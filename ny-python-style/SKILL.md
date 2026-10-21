---
name: ny-python-style
description: 全局 Python 代码风格指南，编写任何 Python 代码时都应使用本技能。
---

# 全局 Python 代码风格指南

## 命名风格

命名风格统一遵循 PEP 8 规范。

## 注释

- 每个代码逻辑段前编写简要注释，描述这段代码做了什么。
- 除 Python 魔术方法外，其他函数需编写文档注释，起始双引号后、末尾双引号前均需换行。
  ```python
  def function():
      """
      函数功能描述。
      """
  ```
- 模块第一行必须添加： `# -*- coding: utf-8 -*-` ，紧接版权注释，然后空两行。注意更新日期。
  ```python
  # -*- coding: utf-8 -*-
  # =================================================
  #  ⠀
  #   Author: Nuoyan <https://github.com/charminglee>
  #   Email : 1279735247@qq.com
  #   Date  : 2026-01-01
  #  ⠀
  # =================================================
  
  
  import something
  ```
- 当一个模块内容较多时，通过 `# region` 分割不同业务代码区域，区域名后接固定 50 个等号：
  ```python
  # region Region Name ==================================================

  
  do_something()
  
  
  # endregion
  ```

## 换行

- 模块顶层每个函数、类、变量、导入之间空两行。例外情况：
  - 同一组逻辑上有关联的变量之间不换行。
  - 导入内部不换行。
- 过长的函数调用、序列、 `if` 语句、函数定义、算术表达式需要换行时，换行风格参考：
  ```python
  # 函数调用
  func(
      param1,
      param2,
      keyword1=False,
      keyword2=True,
  )
  # 序列
  {
      key1: value1,
      key2: value2,
      key3: value3,
  }
  [
      "abc",
      "def",
      "ghi",
  ]
  # if 语句
  if (
      condition1
      and (condition2_1 or condition2_2)
      and (
          condition3 
          or condition4
      )
  ):
      do_something()
  # 函数定义
  def function(
      arg1,
      arg2,
      arg3=0,
  ):
      ...
  # 算术表达式
  value = (
      part1
      + part2_1 * part2_2
      + part3
  )
  ```

## 杂项

- 所有字符串字典 key 和属性名字符串使用单引号，其余字符串使用双引号。
- 表达式判空不要使用 `is not None` / `is None` ，除非表达式需要严格区分 `None` 值。优先使用 `if a` / `if not a` 。
- `dict.get()` 永远是最下策，优先使用 `x in dict` / `x not in dict` 。
