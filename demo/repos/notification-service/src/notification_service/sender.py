"""Sends notifications via AWS SES. No HTTP client needed — uses boto3."""
import boto3
from jinja2 import Environment, FileSystemLoader

ses = boto3.client("ses", region_name="us-east-1")
jinja_env = Environment(loader=FileSystemLoader("templates"))


def send_email(to: str, template_name: str, context: dict) -> dict:
    template = jinja_env.get_template(f"{template_name}.html")
    body = template.render(**context)
    return ses.send_email(
        Source="noreply@company.internal",
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": context.get("subject", "Notification")},
            "Body": {"Html": {"Data": body}},
        },
    )
