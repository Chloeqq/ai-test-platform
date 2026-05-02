from openai import OpenAI
client = OpenAI()
try:
    resp = client.chat.completions.create(
        model="doubao-1-5-pro-32k-250115",
        messages=[{"role":"user","content":"测试回复ok"}],
        max_tokens=10
    )
    print("✅ 通了：", resp.choices[0].message.content)
except Exception as e:
    print("❌ 错了：", e)