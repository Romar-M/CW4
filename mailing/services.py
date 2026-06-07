from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import MailingAttempt, Mailing
import logging

logger = logging.getLogger(__name__)

def send_mailing(mailing_id):
    """Отправляет рассылку по ID. Возвращает (success_count, failure_count)."""
    try:
        mailing = Mailing.objects.select_related('message', 'owner').prefetch_related('recipients').get(id=mailing_id)
    except Mailing.DoesNotExist:
        return 0, 0

    now = timezone.now()
    if not (mailing.start_time <= now <= mailing.end_time):
        logger.warning(f'Попытка отправки рассылки #{mailing_id} вне разрешённого времени')
        return 0, 0

    if not mailing.is_active:
        logger.info(f'Рассылка #{mailing_id} отключена')
        return 0, 0

    recipients = mailing.recipients.all()
    attempts = []
    success_count = 0
    failure_count = 0

    for client in recipients:
        try:
            send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[client.email],
                fail_silently=False,
            )
            status = 'success'
            server_response = 'OK'
            success_count += 1
        except Exception as e:
            status = 'failure'
            server_response = str(e)
            failure_count += 1
            logger.error(f'Ошибка отправки клиенту {client.email}: {e}')

        attempts.append(MailingAttempt(
            status=status,
            server_response=server_response,
            mailing=mailing,
            client=client
        ))

    if attempts:
        MailingAttempt.objects.bulk_create(attempts)

    return success_count, failure_count
