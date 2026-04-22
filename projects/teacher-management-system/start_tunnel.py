# 启动ngrok隧道
from pyngrok import ngrok
import os

# 启动隧道连接到本地的5000端口
public_url = ngrok.connect(5000, "http")
print(f"🌐 公网访问地址: {public_url}")
print("⚠️  注意: 这个地址每次重启都会变化")

# 保持运行
input("按回车键停止...")

# 关闭隧道
ngrok.disconnect(public_url)
ngrok.kill()