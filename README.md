# OpenCCF

采用[中国计算机学会（CCF）](https://www.ccf.org.cn/Academic_Evaluation/By_category/)推荐的国际学术会议和期刊目录，抓取的数据包括主刊/子刊，会议及相关的Workshop等。目前支持飞书、我来推送。

实时更新数据，欢迎补充论文解读等内容：
- [汽车安全学术论文](https://www.wolai.com/chao96/fLquksafgYf7qR87vUiwbi)
- [Android安全学术论文](https://www.wolai.com/chao96/7erDH54B8AyMf6zjzD1UN9)
- [Linux Kernel安全学术论文](https://www.wolai.com/chao96/a8UKqApaapvmDfHqDdT5p9)

## 使用方法

为了提高并发性能，可以去[Semantic Scholar](https://api.semanticscholar.org/api-docs/graph)申请API Key，并配置环境变量`S2API_KEY`。

```sh
$ ./install.sh  # 安装

$ python3 openccf.py --help
  ___                    ____ ____ _____ 
 / _ \ _ __   ___ _ __  / ___/ ___|  ___|
| | | | '_ \ / _ \ '_ \| |  | |   | |_   
| |_| | |_) |  __/ | | | |__| |___|  _|  
 \___/| .__/ \___|_| |_|\____\____|_|    
      |_|                                

usage: openccf.py [-h] [--year start:end] [--rule field:type:rank:name] [--category category] [--keywords keywords] [--bot bot]

options:
  -h, --help            show this help message and exit
  --year start:end      e.g. 2020:2015
  --rule field:type:rank:name
                        e.g. NIS:conf:A,B:all
  --category category   e.g. vehicle,android,linux
  --keywords keywords   e.g. keyword1,keyword2
  --bot bot             e.g. feishu
```

### 飞书推送

在飞书中新建应用和多维表格，开通机器人和相应权限：
- 查看、评论、编辑和管理多维表格
- 获取与发送单聊、群组消息

然后填写配置文件或者设置相应的环境变量：

```json
    "feishu": {
        "app_id": {
            "name": "FEISHU_APP_ID",
            "key": ""
        },
        "app_secret": {
            "name": "FEISHU_APP_SECRET",
            "key": ""
        },
        "bot": {
            "name": "FEISHU_BOT",
            "key": ""
        },
        "bitable": {
            "vehicle": {
                "name": "FEISHU_BITABLE_VEHICLE",
                "key": ""
            },
            "android": {
                "name": "FEISHU_BITABLE_ANDROID",
                "key": ""
            },
            "linux": {
                "name": "FEISHU_BITABLE_LINUX",
                "key": ""
            }
        }
    },
```

### 我来推送

在我来中新建应用和数据表格，然后填写配置文件或者设置相应的环境变量：

```json
    "wolai": {
        "app_id": {
            "name": "WOLAI_APP_ID",
            "key": ""
        },
        "app_secret": {
            "name": "WOLAI_APP_SECRET",
            "key": ""
        },
        "database": {
            "vehicle": {
                "name": "WOLAI_DATABASE_VEHICLE",
                "key": ""
            },
            "android": {
                "name": "WOLAI_DATABASE_ANDROID",
                "key": ""
            },
            "linux": {
                "name": "WOLAI_DATABASE_LINUX",
                "key": ""
            }
        }
    },
```

## TODO

1. ACM digital library的反爬机制可能导致IP被封。
  - IP代理：https://www.scraperapi.com/
2. 增加其他期刊和会议。
  - https://csrankings.org/
  - http://jianying.space/conference-ranking.html
  - https://people.engr.tamu.edu/guofei/sec_conf_stat.htm
3. 基于爬取的论文构建类ChatGPT知识库
  - https://github.com/bhaskatripathi/pdfGPT
  - https://github.com/guangzhengli/ChatFiles
  - https://forum.inner.chj.cloud/archives/1683687612171

## 关注我们

[VulnTotal安全](https://github.com/VulnTotal-Team)致力于分享高质量原创文章和开源工具，包括物联网/汽车安全、移动安全、网络攻防等。

GNU General Public License v3.0

[![Stargazers over time](https://starchart.cc/VulnTotal-Team/openccf.svg)](https://starchart.cc/VulnTotal-Team/openccf)
