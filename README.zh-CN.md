# junit-change-report

把两次 JUnit XML 测试结果做成可审查的回归报告。支持 XML 文件或目录，
保留嵌套 suite 路径，报告新增失败、恢复、增删用例、跳过/错误状态变化及
满足绝对和相对阈值的耗时回退。工具不会执行测试命令，也不会联网。

```bash
python -m pip install .
python -m junit_change_report demo --output demo.html
python -m junit_change_report compare before.xml after.xml --output review.html
```

退出码：`0` 表示门禁通过，`1` 表示选定的回归，`2` 表示输入或报告格式
错误。默认只阻止新出现的 failure/error；可用 `--fail-on any-failure`、
`timing`、`regression` 或 `none`。缺少 `time` 会显示 unknown，不当作零。
重复 identity 会报错而不是静默覆盖。DTD/entity 被拒绝；rerun 扩展只给出
警告，本版本不会宣称识别 flaky。

报告可输出单文件 HTML、Markdown、JSON，HTML 字段全部转义且无 CDN。`demo`
可在安装 wheel 后从任意工作目录运行。fixture 来源见
`junit_change_report/fixtures/PROVENANCE.md`。

```bash
python -m unittest discover -s tests -v
```

MIT。
