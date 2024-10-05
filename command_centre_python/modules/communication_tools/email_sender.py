import aiosmtplib
from email.message import EmailMessage


async def send_email(to_email: str, subject: str, content: str):
    message = EmailMessage()
    message["From"] = "your_email@example.com"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(content)

    await aiosmtplib.send(
        message,
        hostname="smtp.example.com",
        port=587,
        username="your_username",
        password="your_password",
        use_tls=True,
    )
