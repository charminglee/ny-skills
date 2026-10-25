#!/usr/bin/env python3
"""绿洲启元（和平精英UGC）API手册与Wiki离线查询工具。

无需任何第三方依赖。用法示例：
  python gpquery.py class AUGCGameMode            # 搜索类名
  python gpquery.py class AActor --detail         # 查看类详情（事件/函数/属性/父类）
  python gpquery.py class AActor --detail --full  # 输出原始JSON
  python gpquery.py enum ExtraPlayerLiveState     # 搜索枚举
  python gpquery.py struct ItemDefineID           # 搜索结构体
  python gpquery.py func GetAllPlayerController   # 搜索全局函数
  python gpquery.py wiki 20052                    # 读取wiki文章（markdown）
  python gpquery.py wikisearch 存档 10            # 全文搜索wiki文章
"""
import argparse
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

API_BASE = "https://developer.gp.qq.com/api/"
WIKI_BASE = "https://developer.gp.qq.com/wikieditor/_api/"

INDEXES = {
    "class": "class/list/sorted_list.json",
    "enum": "cppenum/list/sorted_list.json",
    "struct": "cppstruct/list/sorted_list.json",
    "func": "globalfunc/list/sorted_list.json",
}

CACHE_DIR = os.path.join(tempfile.gettempdir(), "gpugc_cache")
CACHE_TTL = 24 * 3600  # 索引缓存一天


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gpugc-query/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _fetch_cached(rel_path, no_cache=False):
    """下载 API_BASE 下的文件，带本地缓存（仅索引类JSON）。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = rel_path.replace("/", "_").replace("\\", "_")
    cache_file = os.path.join(CACHE_DIR, safe)
    if not no_cache and os.path.exists(cache_file):
        if time.time() - os.path.getmtime(cache_file) < CACHE_TTL:
            with open(cache_file, encoding="utf-8") as f:
                return f.read()
    data = _http_get(API_BASE + rel_path)
    with open(cache_file, "w", encoding="utf-8") as f:
        f.write(data)
    return data


def _flatten_pairs(obj, out):
    """把 {a:{b:{name:path}}} 嵌套索引拍平成 [(name, path), ...]。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                out.append((k, v))
            else:
                _flatten_pairs(v, out)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and "Name" in item and "Path" in item:
                out.append((item["Name"], item["Path"]))


def _load_index(kind, no_cache=False):
    data = json.loads(_fetch_cached(INDEXES[kind], no_cache))
    pairs = []
    _flatten_pairs(data, pairs)
    # 按（去重后的）名字保留，路径取第一个
    seen = {}
    for name, path in pairs:
        seen.setdefault(name, path)
    return seen


def _search(kind, pattern, no_cache=False):
    idx = _load_index(kind, no_cache)
    p = pattern.lower()
    exact = idx.get(pattern) or idx.get(p)
    results = [(n, pa) for n, pa in sorted(idx.items()) if p in n.lower()]
    if exact:
        results.insert(0, (pattern if pattern in idx else results[0][0], exact))
    return results


def _print_pairs(results):
    if not results:
        print("（无匹配结果）")
        return
    for name, path in results:
        print(f"{name:45s} {path}")


def _fetch_detail(kind, name_or_path, no_cache=False):
    """按路径或名称取类详情JSON。"""
    if "/" in name_or_path:
        rel = name_or_path
    else:
        idx = _load_index(kind, no_cache)
        rel = idx.get(name_or_path)
        if not rel:
            raise SystemExit(f"未找到 {name_or_path}，先用 `class <关键词>` 搜索。")
    return json.loads(_http_get(API_BASE + urllib.parse.quote(rel)))


def cmd_class(args):
    if not args.pattern:
        raise SystemExit("用法：class <名称或路径> [--detail] [--full]")
    if args.detail or args.full:
        d = _fetch_detail("class", args.pattern, args.no_cache)
        if args.full:
            print(json.dumps(d, ensure_ascii=False, indent=2))
            return
        print(f"=== {d.get('Name')} ===")
        desc = d.get("Description")
        if desc:
            print("描述:", desc.strip()[:500])
        parents = d.get("Parents")
        if parents:
            names = [p if isinstance(p, str) else p.get("Name", "?") for p in parents]
            print("父类/接口:", ", ".join(names))
        for key, title in (("Variables", "属性"), ("Functions", "函数"),
                           ("Event", "可重载事件"), ("Delegate", "委托")):
            v = d.get(key)
            if isinstance(v, list) and v:
                names = [x.get("Name", "?") if isinstance(x, dict) else str(x) for x in v]
                print(f"{title} ({len(v)}):")
                for n in names:
                    print(f"  - {n}")
        return
    _print_pairs(_search("class", args.pattern, args.no_cache))


def cmd_enum(args):
    _print_pairs(_search("enum", args.pattern, args.no_cache))


def cmd_struct(args):
    _print_pairs(_search("struct", args.pattern, args.no_cache))


def cmd_func(args):
    _print_pairs(_search("func", args.pattern, args.no_cache))


def cmd_wiki(args):
    url = WIKI_BASE + "query-articles?Id=" + urllib.parse.quote(str(args.id))
    d = json.loads(_http_get(url))
    if d.get("code") != 0 or not d.get("data"):
        raise SystemExit(f"查询失败: {d}")
    art = d["data"][0]
    print(f"# {art['Title']}  (Id={art['Id']})\n")
    print(art["Body"])


def cmd_wikisearch(args):
    count = args.count or 10
    url = (WIKI_BASE + "fulltext-search?Key=" + urllib.parse.quote(args.keyword)
           + f"&page=1&count={count}")
    d = json.loads(_http_get(url))
    if d.get("code") != 0:
        raise SystemExit(f"搜索失败: {d.get('message')}")
    items = d.get("data") or []
    if not items:
        print("（无匹配文章）")
        return
    for it in items:
        print(f"Id={it['Id']:8s} {it['Title']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="绿洲启元API手册与Wiki查询工具")
    ap.add_argument("--no-cache", action="store_true", help="跳过索引缓存")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("class", help="搜索类名 / --detail 查看类详情")
    p.add_argument("pattern")
    p.add_argument("--detail", action="store_true", help="获取类详情（描述/父类/事件/函数/属性）")
    p.add_argument("--full", action="store_true", help="输出原始JSON")
    p.set_defaults(fn=cmd_class)

    for kind, help_ in (("enum", "搜索枚举"), ("struct", "搜索结构体"), ("func", "搜索全局函数")):
        p = sub.add_parser(kind, help=help_)
        p.add_argument("pattern")
        p.set_defaults(fn={"enum": cmd_enum, "struct": cmd_struct, "func": cmd_func}[kind])

    p = sub.add_parser("wiki", help="按Id读取wiki文章")
    p.add_argument("id")
    p.set_defaults(fn=cmd_wiki)

    p = sub.add_parser("wikisearch", help="全文搜索wiki文章")
    p.add_argument("keyword")
    p.add_argument("count", nargs="?", type=int, default=10)
    p.set_defaults(fn=cmd_wikisearch)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
