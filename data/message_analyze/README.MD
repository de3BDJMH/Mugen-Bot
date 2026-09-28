## 数据库文件说明

### config.json

{
    "default":{//默认AI配置
        "protocol": "openai",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
        "credential": "default"
    },
    "groups":{//各个群各自的配置
        "群号":{
            "ai":{//每个群自己的配置
                "protocol": "openai",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-flash",
                "credential": "default"
            },
            "features":{//功能配置，需要可拓展，可能会加入更多功能
                "daily": {
                    "enabled": true//这个每个都必须有
                },
                "weekly": {
                    "enabled": true
                },
                "profile": {
                    "enabled": false
                }
            }
        }
    }
}

字段说明：
- protocol: 协议，支持openai/anthropic/gemini，DeepSeek、GPT第一个，Claude第二个，Gemini第三个，目前只提供第一个，后面两个国内访问太烦了...
- base_url: 接口，只有openai需要填，后面两个都是默认值
- model: 模型，对话模型
- credential: 该群聊使用的API Key别名，用于从credentials.json中获取api

### credentials.json

保存各个群聊自己配置的API Key，并提供默认的key（也就是我自己的）

{
    "default": "sk-xxx",
    "API Key别名": "key"
}
