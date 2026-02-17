import requests
DISCORD_URL = "https://discordapp.com/api/webhooks/1473026116825645210/9eR_UIp-YtDqgKem9q4cD9L2wXrqWZspPaDhTLB6HjRQyLZU-gaUCKvKbf2grX7msal3"
payload = {"content": "🚀 トモユキさん、接続テストです！これが届いたらDiscordの設定は完璧です。"}
res = requests.post(DISCORD_URL, json=payload)
print(f"送信結果: {res.status_code}")
