from media import storage
from platforms.core.ports import TargetRepository
from platforms.core.publishing import MediaInfo, PublicationDraft, PublishJob

from .models import PublicationTarget


class DjangoTargetRepository(TargetRepository):
    def job_of(self, target_id: int) -> PublishJob:
        target = PublicationTarget.objects.select_related(
            "publication", "publication__asset", "social_account"
        ).get(pk=target_id)
        return self.job_from(target)

    @staticmethod
    def job_from(target: PublicationTarget) -> PublishJob:
        publication = target.publication
        asset = publication.asset
        draft = PublicationDraft(
            title=publication.title,
            description=publication.description,
            hashtags=tuple(publication.hashtags),
            media=MediaInfo(asset.size_bytes, asset.mime_type, asset.duration_seconds),
            settings=target.settings or {},
        )
        return PublishJob(
            target_id=target.pk,
            platform=target.platform,
            account_id=target.social_account_id,
            external_id=target.social_account.external_id,
            draft=draft,
            video_path=storage.absolute(asset.storage_path),
            publish_at=publication.publish_at,
            uploaded_media_id=target.uploaded_media_id,
            resume_state=target.resume_state,
        )

    def save_resume_state(self, target_id: int, state: dict | None) -> None:
        PublicationTarget.objects.filter(pk=target_id).update(resume_state=state)
