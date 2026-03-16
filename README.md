# 🧠 selfmem

> 为 OpenClaw Agent 提供自托管的持久化记忆服务。数据完全存储在你自己的服务器上，零第三方依赖。

---

## 特性

- ✅ **数据主权** — 所有记忆数据存储在你自己的服务器，不上传任何第三方
- ✅ **语义搜索** — 基于向量相似度检索相关记忆，而非简单关键词匹配
- ✅ **跨会话持久化** — Agent 重启、服务器重启后记忆不丢失
- ✅ **兼容 mem9 接口** — 可直接替换 mem9 云服务，无需修改 OpenClaw 插件
- ✅ **一键部署** — Docker Compose 一条命令启动所有服务
- ✅ **中英文支持** — 使用 `paraphrase-multilingual-MiniLM-L12-v2` 模型，支持50+语言

---

## 快速开始

### 前置要求

- Docker + Docker Compose
- OpenClaw 已部署

### 部署步骤

**1. 克隆项目**

```bash
git clone https://github.com/gexianmeng/selfmem.git
cd selfmem
```

**2. 修改 API Key**

编辑 `docker-compose.yml`，将 `changeme` 替换为你自己的密钥：

```yaml
environment:
  - API_KEY=你的自定义密钥
```

**3. 启动服务**

```bash
docker compose up -d
```

首次启动会自动下载模型（约 180MB），稍等 1~2 分钟。

**4. 验证服务**

```bash
curl http://localhost:8765/healthz
# 返回 {"status":"ok"} 即为成功
```

**5. 配置 OpenClaw**

修改 `openclaw.json`：

```json
{
  "plugins": {
    "slots": { "memory": "mem9" },
    "entries": {
      "mem9": {
        "enabled": true,
        "config": {
          "apiUrl": "http://localhost:8765",
          "apiKey": "你的自定义密钥"
        }
      }
    },
    "allow": ["mem9"]
  }
}
```

重启 OpenClaw 即可生效。

---

## 通过 SKILL.md 自动部署

将 `SKILL.md` 导入 OpenClaw 后，Agent 会自动引导完成所有部署步骤，用户无需手动执行任何命令。

---

## API 接口

Base URL: `http://localhost:8765`  
认证方式: Header `X-API-Key: <your-api-key>`

| 方法   | 路径                                | 说明         |
| ------ | ----------------------------------- | ------------ |
| GET    | `/healthz`                          | 健康检查     |
| POST   | `/v1alpha2/mem9s/memories`          | 创建记忆     |
| GET    | `/v1alpha2/mem9s/memories?q=关键词` | 语义搜索     |
| GET    | `/v1alpha2/mem9s/memories/{id}`     | 按 ID 获取   |
| PUT    | `/v1alpha2/mem9s/memories/{id}`     | 更新记忆     |
| DELETE | `/v1alpha2/mem9s/memories/{id}`     | 删除记忆     |
| POST   | `/v1alpha2/mem9s/imports`           | 导入文件     |
| GET    | `/v1alpha2/mem9s/imports`           | 查看导入任务 |

---

## 技术栈

| 组件          | 说明                                          |
| ------------- | --------------------------------------------- |
| FastAPI       | REST API 框架                                 |
| Qdrant        | 向量数据库，存储和检索记忆                    |
| sentence-transformers | CPU 友好的 Embedding 模型，支持中英文 |

---

## 数据迁移

**备份：**
```bash
docker compose down
tar -czf selfmem-backup.tar.gz ~/selfmem/
```

**恢复（新服务器）：**
```bash
tar -xzf selfmem-backup.tar.gz
cd selfmem
docker compose up -d
```

openclaw.json 里的 `apiKey` 保持不变，记忆自动恢复。

---

## License

MIT
