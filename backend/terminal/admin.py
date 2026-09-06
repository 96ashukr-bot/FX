from django.contrib import admin

from .models import AccountSnapshot, ExecutionEvent, ExecutionNode, TerminalCommand

admin.site.register((ExecutionNode, TerminalCommand, ExecutionEvent, AccountSnapshot))
