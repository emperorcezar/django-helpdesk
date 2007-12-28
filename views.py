"""                                     .. 
                                 .,::;::::::
                           ..,::::::::,,,,:::      Jutda Helpdesk - A Django
                      .,,::::::,,,,,,,,,,,,,::     powered ticket tracker for
                  .,::::::,,,,,,,,,,,,,,,,,,:;r.        small enterprise
                .::::,,,,,,,,,,,,,,,,,,,,,,:;;rr.
              .:::,,,,,,,,,,,,,,,,,,,,,,,:;;;;;rr      (c) Copyright 2008
            .:::,,,,,,,,,,,,,,,,,,,,,,,:;;;:::;;rr
          .:::,,,,,,,,,,,,,,,,,,,,.  ,;;;::::::;;rr           Jutda
        .:::,,,,,,,,,,,,,,,,,,.    .:;;:::::::::;;rr
      .:::,,,,,,,,,,,,,,,.       .;r;::::::::::::;r;   All Rights Reserved
    .:::,,,,,,,,,,,,,,,        .;r;;:::::::::::;;:.
  .:::,,,,,,,,,,,,,,,.       .;r;;::::::::::::;:.
 .;:,,,,,,,,,,,,,,,       .,;rr;::::::::::::;:.   This software is released 
.,:,,,,,,,,,,,,,.    .,:;rrr;;::::::::::::;;.  under a limited-use license that
  :,,,,,,,,,,,,,..:;rrrrr;;;::::::::::::;;.  allows you to freely download this
   :,,,,,,,:::;;;rr;;;;;;:::::::::::::;;,  software from it's manufacturer and
    ::::;;;;;;;;;;;:::::::::::::::::;;,  use it yourself, however you may not
    .r;;;;:::::::::::::::::::::::;;;,  distribute it. For further details, see
     .r;::::::::::::::::::::;;;;;:,  the enclosed LICENSE file.
      .;;::::::::::::::;;;;;:,.
       .;;:::::::;;;;;;:,.  Please direct people who wish to download this
        .r;;;;;;;;:,.  software themselves to www.jutda.com.au.
          ,,,..

$Id$

"""
# Python imports
from datetime import datetime

# Django imports
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.template import loader, Context, RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect
from django.db.models import Q

# Helpdesk imports
from helpdesk.forms import TicketForm
from helpdesk.models import Ticket, Queue, FollowUp, TicketChange

def dashboard(request):
    tickets = Ticket.objects.filter(assigned_to=request.user).exclude(status=Ticket.CLOSED_STATUS)
    unassigned_tickets = Ticket.objects.filter(assigned_to__isnull=True).exclude(status=Ticket.CLOSED_STATUS)
    
    dash_tickets = []
    for q in Queue.objects.all():
        dash_tickets.append({
            'queue': q,
            'open': q.ticket_set.filter(Q(status=Ticket.OPEN_STATUS) | Q(status=Ticket.REOPENED_STATUS)).count(),
            'resolved': q.ticket_set.filter(status=Ticket.RESOLVED_STATUS).count(),
        })

    return render_to_response('helpdesk/dashboard.html',
        RequestContext(request, {
            'user_tickets': tickets,
            'unassigned_tickets': unassigned_tickets,
            'dash_tickets': dash_tickets,
        }))
dashboard = login_required(dashboard)

def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.GET.has_key('take'):
        ticket.assigned_to = request.user
        ticket.save()

    return render_to_response('helpdesk/ticket.html',
        RequestContext(request, {
            'ticket': ticket,
            'active_users': User.objects.filter(is_active=True),
        }))
view_ticket = login_required(view_ticket)

def update_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    comment = request.POST.get('comment', '')
    new_status = int(request.POST.get('new_status', ticket.status))
    title = request.POST.get('title', '')
    public = request.POST.get('public', False)
    owner = int(request.POST.get('owner', None))
    if not owner and ticket.assigned_to:
        owner = ticket.assigned_to.id

    f = FollowUp(ticket=ticket, date=datetime.now(), comment=comment, user=request.user)
    if public:
        f.public = True

    if owner:
        if owner != 0 and (ticket.assigned_to and owner != ticket.assigned_to.id) or not ticket.assigned_to:
            new_user = User.objects.get(id=owner)
            f.title = 'Assigned to %s' % new_user.username
            ticket.assigned_to = new_user
        else:
            f.title = 'Unassigned'
            ticket.assigned_to = None
    
    if new_status != ticket.status:
        ticket.status = new_status
        ticket.save()
        f.new_status = new_status
        if f.title:
            f.title += ' and %s' % ticket.get_status_display()
        else:
            f.title = '%s' % ticket.get_status_display()

    if not f.title:
        if f.comment:
            f.title = 'Comment'
        else:
            f.title = 'Updated'

    f.save()
    
    if title != ticket.title:
        c = TicketChange(followup=f, field='Title', old_value=ticket.title, new_value=title)
        c.save()
        ticket.title = title

    ticket.save()
            
    return HttpResponseRedirect(ticket.get_absolute_url())
update_ticket = login_required(update_ticket)

def ticket_list(request):
    tickets = Ticket.objects.select_related()
    context = {}

    ### FILTERING
    queues = request.GET.getlist('queue')
    if queues:
        queues = [int(q) for q in queues]
        tickets = tickets.filter(queue__id__in=queues)
        context = dict(context, queues=queues)

    owners = request.GET.getlist('assigned_to')
    if owners:
        owners = [int(u) for u in owners]
        tickets = tickets.filter(assigned_to__id__in=owners)
        context = dict(context, owners=owners)

    statuses = request.GET.getlist('status')
    if statuses:
        statuses = [int(s) for s in statuses]
        tickets = tickets.filter(status__in=statuses)
        context = dict(context, statuses=statuses)
   
    ### SORTING
    sort = request.GET.get('sort', None)
    if sort not in ('status', 'assigned_to', 'created', 'title', 'queue'):
        sort = 'created'
    tickets = tickets.order_by(sort)
    context = dict(context, sort=sort)

    return render_to_response('helpdesk/ticket_list.html',
        RequestContext(request, dict(
            context,
            tickets=tickets,
            user_choices=User.objects.filter(is_active=True),
            queue_choices=Queue.objects.all(),
            status_choices=Ticket.STATUS_CHOICES,
        )))
ticket_list = login_required(ticket_list)

def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in User.objects.filter(is_active=True)]
        if form.is_valid():
            ticket = form.save(user=request.user)
            return HttpResponseRedirect(ticket.get_absolute_url())
    else:
        form = TicketForm()
        form.fields['queue'].choices = [('', '--------')] + [[q.id, q.title] for q in Queue.objects.all()]
        form.fields['assigned_to'].choices = [('', '--------')] + [[u.id, u.username] for u in User.objects.filter(is_active=True)]

    return render_to_response('helpdesk/create_ticket.html', 
        RequestContext(request, {
            'form': form,
        }))
create_ticket = login_required(create_ticket)