from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Client, Message, Mailing
from .forms import ClientForm, MessageForm, MailingForm
from .services import send_mailing
from django.utils import timezone

# --- Клиенты ---
class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'mailing/client_list.html'
    context_object_name = 'clients'

    def get_queryset(self):
        user = self.request.user
        if user.has_perm('mailing.can_view_all_clients'):
            return Client.objects.all()
        return Client.objects.filter(owner=user)

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    form_class = ClientForm
    success_url = reverse_lazy('mailing:client_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class ClientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Client
    form_class = ClientForm
    success_url = reverse_lazy('mailing:client_list')

    def test_func(self):
        client = self.get_object()
        return self.request.user == client.owner

class ClientDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Client
    success_url = reverse_lazy('mailing:client_list')

    def test_func(self):
        client = self.get_object()
        return self.request.user == client.owner

# --- Сообщения ---
class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'mailing/message_list.html'
    context_object_name = 'messages'

    def get_queryset(self):
        return Message.objects.filter(owner=self.request.user)

class MessageCreateView(LoginRequiredMixin, CreateView):
    model = Message
    form_class = MessageForm
    success_url = reverse_lazy('mailing:message_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class MessageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    form_class = MessageForm
    success_url = reverse_lazy('mailing:message_list')

    def test_func(self):
        return self.get_object().owner == self.request.user

class MessageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    success_url = reverse_lazy('mailing:message_list')

    def test_func(self):
        return self.get_object().owner == self.request.user

# --- Рассылки ---
class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = 'mailing/mailing_list.html'
    context_object_name = 'mailings'

    def get_queryset(self):
        user = self.request.user
        if user.has_perm('mailing.can_view_all_mailings'):
            return Mailing.objects.all().prefetch_related('recipients', 'message')
        return Mailing.objects.filter(owner=user).prefetch_related('recipients', 'message')

class MailingDetailView(LoginRequiredMixin, DetailView):
    model = Mailing
    template_name = 'mailing/mailing_detail.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.update_status()   # динамическое обновление статуса
        return obj

class MailingCreateView(LoginRequiredMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    success_url = reverse_lazy('mailing:mailing_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.status = 'created'
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user.has_perm('mailing.can_view_all_clients'):
            form.fields['recipients'].queryset = Client.objects.all()
        else:
            form.fields['recipients'].queryset = Client.objects.filter(owner=user)
        form.fields['message'].queryset = Message.objects.filter(owner=user)
        return form

class MailingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    success_url = reverse_lazy('mailing:mailing_list')

    def test_func(self):
        return self.get_object().owner == self.request.user

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user
        if user.has_perm('mailing.can_view_all_clients'):
            form.fields['recipients'].queryset = Client.objects.all()
        else:
            form.fields['recipients'].queryset = Client.objects.filter(owner=user)
        form.fields['message'].queryset = Message.objects.filter(owner=user)
        return form

class MailingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Mailing
    success_url = reverse_lazy('mailing:mailing_list')

    def test_func(self):
        return self.get_object().owner == self.request.user

def run_mailing_manual(request, pk):
    mailing = get_object_or_404(Mailing, id=pk)
    user = request.user
    if not (user == mailing.owner or user.has_perm('mailing.can_view_all_mailings')):
        messages.error(request, 'Нет прав для запуска этой рассылки.')
        return redirect('mailing:mailing_list')

    mailing.update_status()
    now = timezone.now()
    if mailing.start_time <= now <= mailing.end_time and mailing.is_active:
        success, failure = send_mailing(mailing.id)
        messages.success(request, f'Рассылка выполнена. Успешно: {success}, ошибок: {failure}.')
    else:
        messages.error(request, 'Рассылка не может быть запущена (неактивна, либо время не в диапазоне, либо отключена).')
    return redirect('mailing:mailing_detail', pk=pk)

# --- Главная страница со статистикой (кеширование) ---
from django.views.generic import TemplateView
from django.core.cache import cache

class HomeView(TemplateView):
    template_name = 'mailing/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cache_key = 'home_stats'
        stats = cache.get(cache_key)
        if not stats:
            total_mailings = Mailing.objects.count()
            now = timezone.now()
            active_mailings = Mailing.objects.filter(
                start_time__lte=now,
                end_time__gte=now,
                is_active=True
            ).count()
            unique_clients = Client.objects.values('email').distinct().count()
            stats = {
                'total_mailings': total_mailings,
                'active_mailings': active_mailings,
                'unique_clients': unique_clients,
            }
            cache.set(cache_key, stats, 60*10)  # 10 минут
        context.update(stats)
        return context