---
name: ny-json-style
description: 全局 JSON 风格指南，编写任何正式 JSON 代码时都应使用本技能，临时生成、测试生成的 JSON 无需遵循。
---

# 全局 JSON 风格指南

全局 JSON 风格指南，编写任何正式 JSON 代码时都应使用本技能，临时生成、测试生成的 JSON 无需遵循。

## 缩进与格式化

- JSON 需进行格式化，且使用 4 个空格缩进。

## 字段

- 所有字段必须另起一行。

  ```json
  {
      "field1": {
        "field2": "value",
        "field3": "value"
      }
  }
  ```

## 数组

- 纯数字数组，每个元素不换行。

  ```json
  {
      "number_array": [1, 2, 3, 4, 5]
  }
  ```
  
- 字符串数组，包括纯字符串数组和字符串数字混合数组，每个元素独占一行。

  ```json
  {
      "string_array": [
          "apple", 
          "chicken", 
          "people"
      ],
      "string_number_array": [
          "apple", 
          1,
          "chicken", 
          "people", 
          2
      ]
  }
  ```
  