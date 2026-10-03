from django.db import migrations

PROCESSING = "processing"
LEGACY_FAILURES = {
    "network": "network",
    "authentication": "grant_revoked",
    "authorization": "scope_missing",
    "rate_limit": "rate_limited",
    "platform": "refused",
    "validation": "invalid",
    "file": "file_rejected",
    "unknown": "unexpected",
}
UNCONFIRMED_MARKS = ("may have been created", "did not confirm")


def _failure_of(error: dict) -> dict:
    message = str(error.get("message") or "")
    failure = LEGACY_FAILURES.get(error.get("type"), "unexpected")
    if any(mark in message for mark in UNCONFIRMED_MARKS):
        failure = "unconfirmed"
    return {"failure": failure, "message": message, "details": str(error.get("details") or "")}


def adopt_platform_failures(apps, schema_editor):
    PublicationTarget = apps.get_model("publishing", "PublicationTarget")
    PublicationTarget.objects.exclude(status=PROCESSING).exclude(confirmation_state=None).update(
        confirmation_state=None
    )
    rows = PublicationTarget.objects.exclude(error=None).only("pk", "error").iterator()
    for target in rows:
        error = target.error
        if isinstance(error, dict) and "type" in error and "failure" not in error:
            PublicationTarget.objects.filter(pk=target.pk).update(error=_failure_of(error))


class Migration(migrations.Migration):
    dependencies = [("publishing", "0003_commit_marker")]

    operations = [
        migrations.RenameField("publicationtarget", "resume_state", "confirmation_state"),
        migrations.RunPython(adopt_platform_failures, migrations.RunPython.noop),
    ]
