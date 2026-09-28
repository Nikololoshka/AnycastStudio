from datetime import UTC, datetime

from django.db import migrations

LEGACY_MARKER = "posting_started"
COMMIT_MARKER = "commit_started"


def _marker_time(value) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).isoformat()
    return str(value)


def rename_commit_marker(apps, schema_editor):
    PublicationTarget = apps.get_model("publishing", "PublicationTarget")
    for target in PublicationTarget.objects.exclude(resume_state=None).only("pk", "resume_state").iterator():
        state = target.resume_state
        if not isinstance(state, dict) or LEGACY_MARKER not in state:
            continue
        renamed = {key: value for key, value in state.items() if key != LEGACY_MARKER}
        renamed[COMMIT_MARKER] = _marker_time(state[LEGACY_MARKER])
        PublicationTarget.objects.filter(pk=target.pk).update(resume_state=renamed)


class Migration(migrations.Migration):
    dependencies = [("publishing", "0002_target_last_activity")]

    operations = [migrations.RunPython(rename_commit_marker, migrations.RunPython.noop)]
