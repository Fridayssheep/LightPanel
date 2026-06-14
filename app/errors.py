class AgentConfigError(RuntimeError):
    """模型智能体缺少配置、无法启动时抛出。"""


class AgentExecutionError(RuntimeError):
    """模型智能体在规划或调用工具失败时抛出。"""
