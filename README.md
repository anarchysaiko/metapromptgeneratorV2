# 元提示词生成器V2

元提示词生成器是一个基于 Gradio 的 Web 应用程序，用于生成 AI 模型的提示词模板。它支持 Claude 和 OpenAI 的元提示词实现，可以根据用户输入的任务描述和变量生成相应的提示词模板。

## 在线体验

您可以通过以下链接在线体验元提示词生成器：

[在线体验元提示词生成器](https://www.modelscope.cn/studios/anarchysaiko/metapromptgenerator)

## 功能特点

- 支持 Claude 和 OpenAI 的元提示词实现
- 可自定义任务描述和变量
- 自动处理和提取变量
- 支持通过环境变量或用户输入提供 API 密钥和其他配置
- 友好的 Web 界面，支持实时生成提示词模板

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/anarchysaiko/metapromptgeneratorV2.git

cd metapromptgeneratorV2
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

1. 设置环境变量（可选）：

```bash
export MODEL_NAME="your_model_name"
export API_KEY="your_api_key"
export BASE_URL="your_api_base_url"
```

2. 运行应用：

```bash
python app.py
```

3. 在浏览器中打开显示的 URL（通常是 `http://127.0.0.1:7860`）。

4. 在 Web 界面中：
   - 输入任务描述
   - 输入变量（可选，用英文逗号分隔）
   - 选择 Metaprompt 实现（Claude 或 OpenAI）
   - 如果没有设置环境变量，请填写模型名称、API 密钥和 API 基础 URL
   - 点击"生成提示词"按钮

5. 等待生成结果（可能需要 1-2 分钟）

6. 查看生成的提示词模板和提取的变量

## 注意事项

- API 密钥等敏感信息请妥善保管，不要上传到公共仓库
- 生成过程可能需要一些时间，请耐心等待
- 如果遇到问题，请查看控制台输出的日志信息

## 贡献

欢迎提交 Issues 和 Pull Requests 来帮助改进这个项目。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。
