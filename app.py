import gradio as gr
from openai import OpenAI
import re
from openai import APITimeoutError, APIError
import time
import logging
from metaprompts import CLAUDE_METAPROMPT, OPENAI_METAPROMPT
import os


def get_parameter(user_input, env_var_name, param_name):
    if user_input:
        return user_input
    env_value = os.getenv(env_var_name)
    if env_value:
        return env_value
    raise ValueError(
        f"{param_name} 未提供。请在输入框中填写或设置环境变量 {env_var_name}"
    )


# 创建自定义CSS
custom_css = """
.variable-instructions {
    background-color: #f0f0f0;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 20px;
}
.variable-instructions h4 {
    margin-top: 0;
    color: #333;
}
.wait-message {
    background-color: #fff3cd;
    color: #856404;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 15px;
    text-align: center;
    font-weight: bold;
}
"""


def pretty_print(message):
    if message is None:
        return "None"
    return "\n\n".join(
        "\n".join(
            line.strip()
            for line in re.findall(r".{1,100}(?:\s+|$)", paragraph.strip("\n"))
        )
        for paragraph in re.split(r"\n\n+", message)
    )


def extract_between_tags(tag: str, string: str, strip: bool = False) -> list[str]:
    pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
    ext_list = re.findall(pattern, string, re.DOTALL | re.IGNORECASE)
    if strip:
        ext_list = [e.strip() for e in ext_list]
    return ext_list


def remove_empty_tags(text):
    return re.sub(r"\n<(\w+)>\s*</\1>\n", "", text, flags=re.DOTALL)


def strip_last_sentence(text):
    sentences = text.split(". ")
    if sentences[-1].startswith("Let me know"):
        sentences = sentences[:-1]
        result = ". ".join(sentences)
        if result and not result.endswith("."):
            result += "."
        return result
    else:
        return text


def extract_prompt(message):
    # 首先尝试提取 <Instructions> 标签内的内容
    match = re.search(r"<Instructions>(.*?)</Instructions>", message, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有找到 <Instructions> 标签，尝试提取整个消息内容
    if message.strip():
        return message.strip()

    # 如果消息为空，返回警告
    return "警告：API返回的消息为空"


def extract_variables(variable_string):
    return set(var.strip() for var in variable_string.split(",") if var.strip())


def find_free_floating_variables(text):
    # 匹配 {$VARIABLE} 格式的变量
    pattern = r"\{(\$[A-Z_]+)\}"
    matches = re.findall(pattern, text)
    return set(matches)


def remove_inapt_floating_variables(text):
    variables = find_free_floating_variables(text)
    for var in variables:
        # 这里可以添加更复杂的逻辑来判断变量是否不恰当
        # 现在我们简单地假设所有自由浮动变量是不恰当的
        text = text.replace(f"{{{var}}}", f"[{var[1:]}]")
    return text


def process_variables(variables_input):
    if not variables_input.strip():
        return []
    # 使用英文逗号分隔，去除空白字符，并去除可能存在的引号
    return [
        var.strip().strip("\"'") for var in variables_input.split(",") if var.strip()
    ]


# 核心处理函数
def generate_prompt(
    task,
    variables,
    metaprompt_choice,
    model_name,
    api_key,
    base_url,
    max_retries=3,
    retry_delay=5,
):
    logging.debug(
        f"开始生成提示词，任务：{task}, 变量：{variables}, 选择的metaprompt：{metaprompt_choice}, 模型：{model_name}"
    )

    client = OpenAI(api_key=api_key, base_url=base_url)
    logging.debug(f"创建OpenAI客户端，使用base_url：{base_url}")

    processed_variables = process_variables(variables)
    logging.debug(f"处理后的变量：{processed_variables}")

    # 处理变量
    variable_string = "\n".join([f"{{${var}}}" for var in processed_variables])

    # 根据用户选择使用不同的metaprompt
    if metaprompt_choice == "Claude":
        metaprompt = CLAUDE_METAPROMPT
        prompt = metaprompt.replace("{{TASK}}", task)
        assistant_partial = "<Inputs>"
        if variable_string:
            assistant_partial += (
                variable_string + "\n</Inputs>\n<Instructions Structure>"
            )
        assistant_partial += "\n</Instructions Structure>\n<Instructions>\n"
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": assistant_partial},
        ]
    else:  # OpenAI
        metaprompt = OPENAI_METAPROMPT
        task_with_variables = (
            f"Task, Goal, or Current Prompt:\n{task}\n\nVariables:\n{variable_string}"
        )
        messages = [
            {"role": "system", "content": metaprompt},
            {"role": "user", "content": task_with_variables},
        ]

    # 添加重试逻辑
    for attempt in range(max_retries):
        try:
            logging.debug(f"尝试第 {attempt + 1} 次调用API...")
            response = client.chat.completions.create(
                model=model_name,
                max_tokens=4096,
                messages=messages,
                temperature=0,
                timeout=60,
            )
            message = response.choices[0].message.content
            logging.debug(f"API返回的原始消息：\n{message}")
            break
        except Exception as e:
            logging.error(f"API请求失败: {str(e)}")
            if attempt == max_retries - 1:
                logging.error("达到最大重试次数，放弃请求")
                return "API请求失败", ", ".join(processed_variables)

    # 提取和处理成的提示词模板
    extracted_prompt_template = extract_prompt(message)
    extracted_variables = extract_variables(variables)

    if "警告" in extracted_prompt_template:
        logging.warning(f"提取提示词模板时遇到问题：{extracted_prompt_template}")
    else:
        logging.info("成功提取提示词模板")

    # 处理浮动变量
    floating_variables = find_free_floating_variables(extracted_prompt_template)
    if len(floating_variables) > 0:
        extracted_prompt_template = remove_inapt_floating_variables(
            extracted_prompt_template
        )

    logging.debug(f"生成的提示词模板：{extracted_prompt_template}")
    logging.debug(f"提取的变量：{extracted_variables}")

    return extracted_prompt_template, ", ".join(processed_variables)


# Gradio界面函数
def gradio_interface(task, variables, metaprompt_choice, model_name, api_key, base_url):
    logging.info(
        f"接收到新的请求：任务 = {task}, 变量 = {variables}, metaprompt选择 = {metaprompt_choice}"
    )

    # 显示等待消息
    yield gr.update(visible=True), "", ""

    try:
        model_name = get_parameter(model_name, "MODEL_NAME", "模型名称")
        api_key = get_parameter(api_key, "API_KEY", "API密钥")
        base_url = get_parameter(base_url, "BASE_URL", "API基础URL")

        logging.debug(f"使用的模型名称：{model_name}")
        logging.debug(f"使用的API基础URL：{base_url}")
        # 不要记录 API 密钥，以保护敏感信息

        prompt_template, extracted_variables = generate_prompt(
            task, variables.strip(), metaprompt_choice, model_name, api_key, base_url
        )

        if prompt_template == "API请求失败" or "警告" in prompt_template:
            logging.warning(f"生成提示词失败：{prompt_template}")
            prompt_template = "生成提示词失败：" + prompt_template
        if not extracted_variables:
            logging.warning("未提供变量或提取变量失败")
            extracted_variables = "未提供变量或提取变量失败"

        logging.info("请求处理完成")

    except ValueError as e:
        prompt_template = str(e)
        extracted_variables = ""
        logging.error(f"参数错误：{str(e)}")

    # 隐藏等待消息并返回结果
    yield gr.update(visible=False), prompt_template, extracted_variables


# 创建Gradio界面
with gr.Blocks(css=custom_css) as iface:
    gr.Markdown("# 元提示词生成器")
    gr.Markdown("输入任务描述和变量,生成相应的提示词模板。")

    with gr.Row():
        with gr.Column(scale=1):
            task_input = gr.Textbox(lines=5, label="任务描述")
            variables_input = gr.Textbox(label="变量 (用英文逗号分隔，可选)")
            metaprompt_choice = gr.Radio(
                ["Claude", "OpenAI"], label="选择Metaprompt实现", value="Claude"
            )
            model_name_input = gr.Textbox(label="模型名称", value="")
            api_key_input = gr.Textbox(label="API密钥", value="")
            base_url_input = gr.Textbox(label="API基础URL", value="")
            generate_button = gr.Button("生成提示词")

            gr.HTML(
                """
                <div class="variable-instructions">
                    <h4>变量使用说明：</h4>
                    <ul>
                        <li>用于在提示词模板中插入可变内容</li>
                        <li>多个变量用英文逗号（,）分隔</li>
                        <li>变量名不需要使用引号</li>
                        <li>示例：WTD, SPL, CPL, GAP, RAT, ROF, RCL, RTC, WTDD, RFW</li>
                        <li>如不需要使用变量，可将输入框留空</li>
                    </ul>
                </div>
                """
            )

        with gr.Column(scale=1):
            wait_message = gr.Markdown(
                "**请耐心等待1-2分钟，生成过程可能需要一些时间...**",
                visible=False,
                elem_classes=["wait-message"],
            )
            prompt_output = gr.Textbox(lines=10, label="生成的提示词模板")
            variables_output = gr.Textbox(label="提取的变量")
            # 移除 debug_output

    generate_button.click(
        fn=gradio_interface,
        inputs=[
            task_input,
            variables_input,
            metaprompt_choice,
            model_name_input,
            api_key_input,
            base_url_input,
        ],
        outputs=[wait_message, prompt_output, variables_output],  # 移除 debug_output
    )

# 运行Gradio应用
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    iface.launch()


gr.Markdown(
    """
    注意：模型名称、API密钥和API基础URL可以通过环境变量设置（MODEL_NAME, API_KEY, BASE_URL）。
    如果输入框为空，将使用对应的环境变量值。如果两者都为空，将报错。
"""
)
