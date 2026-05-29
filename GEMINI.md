# Gemini CLI 使用说明

请把 `AGENTS.md` 作为本仓库的标准执行规范。

使用 Gemini CLI 时，建议先确认它已经加载当前目录的上下文文件。如果刚修改过说明文件，可以在 Gemini CLI 中执行：

```text
/memory reload
```

然后要求 Gemini CLI 阅读 `AGENTS.md`，并使用仓库里的脚本执行 3X-UI 面板安装、后台文档生成或客户节点创建任务。不要让它临时重写部署逻辑。
