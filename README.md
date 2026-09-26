# 中国优选 IP 自动订阅

每天北京时间 15:00 自动测试 Cloudflare 官方公布的 IPv4 网段，按延迟筛选 200–500 个可达地址，并生成 Clash、纯文本及 Base64 订阅文件。

> 说明：公网 IP 的可用性、速度和归属会随时间及运营商变化，无法保证固定数量或永久速度。脚本只测试 Cloudflare 官方网段，不扫描任意第三方地址。

## 订阅地址

更新成功后可直接使用以下 Raw 地址：

- Clash/Mihomo：https://raw.githubusercontent.com/erer520/cf/main/data/clash.yaml
- Base64 通用订阅：https://raw.githubusercontent.com/erer520/cf/main/data/base64.txt
- 纯文本地址：https://raw.githubusercontent.com/erer520/cf/main/data/ips.txt

## 本地运行

```bash
pip install -r requirements.txt
python scripts/generate.py --count 300
```

可通过环境变量 `TEST_URL` 指定测试 URL（默认 `https://speed.cloudflare.com/__down?bytes=100000`），通过 `TEST_HOST` 指定 Host；测试地址应是你有权访问的地址。

## 自动化

`.github/workflows/daily.yml` 使用 GitHub Actions 的 `Asia/Shanghai` 时间判断，每日 15:00 触发，也支持手动运行。结果提交到 `data/` 目录。

## 免责声明

仅测试 Cloudflare 官方公开网段和合法的 HTTP(S) 连通性。请遵守当地法律、网络服务商条款及 GitHub Actions 使用政策，不要将生成的地址用于绕过访问控制、攻击或滥用。
