from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

User = get_user_model()

class Client(models.Model):
    email = models.EmailField(unique=True, verbose_name='Email')
    full_name = models.CharField(max_length=255, verbose_name='Ф.И.О.')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Владелец', related_name='clients')

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        permissions = [
            ('can_view_all_clients', 'Может просматривать всех клиентов'),
        ]

class Message(models.Model):
    subject = models.CharField(max_length=255, verbose_name='Тема письма')
    body = models.TextField(verbose_name='Тело письма')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Владелец', related_name='messages')

    def __str__(self):
        return self.subject

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'

class Mailing(models.Model):
    STATUS_CHOICES = (
        ('created', 'Создана'),
        ('started', 'Запущена'),
        ('completed', 'Завершена'),
    )

    start_time = models.DateTimeField(verbose_name='Дата и время начала')
    end_time = models.DateTimeField(verbose_name='Дата и время окончания')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name='Статус')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='mailings', verbose_name='Сообщение')
    recipients = models.ManyToManyField(Client, related_name='mailings', verbose_name='Получатели')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Владелец', related_name='mailings')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError('Дата начала должна быть раньше даты окончания.')
        if self.start_time and self.start_time < timezone.now():
            raise ValidationError('Дата начала не может быть в прошлом.')

    def update_status(self):
        now = timezone.now()
        new_status = None
        if now < self.start_time:
            new_status = 'created'
        elif self.start_time <= now <= self.end_time:
            new_status = 'started'
        else:
            new_status = 'completed'

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status'])
        return self.status

    def __str__(self):
        return f'Рассылка #{self.id} ({self.message.subject})'

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'
        permissions = [
            ('can_view_all_mailings', 'Может просматривать все рассылки'),
            ('can_disable_mailing', 'Может отключать рассылки'),
        ]

class MailingAttempt(models.Model):
    STATUS_CHOICES = (
        ('success', 'Успешно'),
        ('failure', 'Не успешно'),
    )

    attempt_time = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время попытки')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name='Статус')
    server_response = models.TextField(blank=True, verbose_name='Ответ почтового сервера')
    mailing = models.ForeignKey(Mailing, on_delete=models.CASCADE, related_name='attempts', verbose_name='Рассылка')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name='Получатель', null=True)

    class Meta:
        verbose_name = 'Попытка рассылки'
        verbose_name_plural = 'Попытки рассылок'
