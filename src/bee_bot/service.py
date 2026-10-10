"""Authoritative Bee Bot business rules; model text never grants identity or success."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import threading
from uuid import uuid4

from .errors import BeeBotError
from .store import Store

ZONE = ZoneInfo('Asia/Ho_Chi_Minh')
TERMINAL = {'completed', 'cancelled', 'approval_withdrawn', 'expired'}
LOCKED = {'reserved', 'updating', 'reconciliation_required', 'write_failed'}
SIGNATURE = ('assignment_id', 'shift_id', 'coach_id', 'starts_at', 'ends_at',
             'room', 'site', 'class_name', 'revision')


def moment(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise BeeBotError('INVALID_TIME', 'Thời điểm phải là ISO 8601 có múi giờ.')
    if result.tzinfo is None:
        raise BeeBotError('INVALID_TIME', 'Thời điểm cần múi giờ.')
    return result


def overlaps(a, b):
    return moment(a['starts_at']) < moment(b['ends_at']) and moment(b['starts_at']) < moment(a['ends_at'])


class BeeBotService:
    def __init__(self, db_path, schedule, clock=None):
        self.store = Store(db_path)
        self.schedule = schedule
        self.clock = clock or (lambda: datetime.now(ZONE))
        self._lock = threading.RLock()

    def close(self):
        self.store.close()

    def _now(self):
        value = self.clock()
        if value.tzinfo is None:
            raise BeeBotError('INVALID_TIME', 'Clock cần múi giờ.')
        return value

    def _actor(self, actor, ops=False):
        person = next((p for p in self.schedule.list_people() if p['person_id'] == actor), None)
        if not person or not person.get('active', False):
            raise BeeBotError('UNAUTHORIZED', 'Danh tính chưa được xác thực hoặc đã ngừng hoạt động.')
        if ops and person['role'] != 'ops':
            raise BeeBotError('FORBIDDEN', 'Chỉ vận hành được thực hiện thao tác này.')
        return person

    def _recipient(self, person_id, owner):
        person = self._actor(person_id)
        if person['role'] != 'labcoach' or person_id == owner:
            raise BeeBotError('INVALID_RECIPIENT', 'Người nhận phải là labcoach khác đang hoạt động.')
        return person

    def _get(self, kind, identifier):
        value = self.store.get(kind, identifier)
        if not value:
            raise BeeBotError('NOT_FOUND', 'Không tìm thấy bản ghi.')
        return value

    def _mutation(self, actor, operation, event_id, callback):
        self._actor(actor)
        if not isinstance(event_id, str) or not event_id.strip():
            raise BeeBotError('EVENT_ID_REQUIRED', 'Thiếu mã sự kiện bên ngoài.')
        with self._lock:
            db = self.store.connection
            db.execute('BEGIN IMMEDIATE')
            try:
                saved = db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
                if saved:
                    if saved['actor'] != actor or saved['operation'] != operation:
                        raise BeeBotError('EVENT_CONFLICT', 'Mã sự kiện đã được sử dụng cho thao tác khác.')
                    result = json.loads(saved['result'])
                    # An interrupted write saves its intent before touching the sheet.
                    # Recovery can reconcile that intent after this event was saved;
                    # a replay must report the reconciled result, never repeat the write.
                    if operation == 'respond_to_invitation' and result.get('request_id'):
                        current = self.store.get('request', result['request_id'])
                        if current and result.get('status') in LOCKED:
                            result = current
                    db.commit()
                    return result
                self._event = (event_id, actor, operation)
                result = callback()
                self._save_event(result)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
            finally:
                self._event = None

    def _save_event(self, result):
        event_id, actor, operation = self._event
        self.store.connection.execute('INSERT INTO events(id,actor,operation,result) VALUES(?,?,?,?) '
                                      'ON CONFLICT(id) DO UPDATE SET result=excluded.result',
                                      (event_id, actor, operation, json.dumps(result, ensure_ascii=False)))

    def _new(self, prefix, key, **fields):
        identifier = prefix + '-' + uuid4().hex[:12]
        return {'id': identifier, key: identifier, **fields}

    def _notify(self, recipients, event, **details):
        for recipient in dict.fromkeys(recipients):
            self.store.put('notification', self._new('NT', 'notification_id',
                recipient_id=recipient, event=event, created_at=self._now().isoformat(),
                delivery_status='pending', **details))

    def _ops(self):
        return [p['person_id'] for p in self.schedule.list_people()
                if p.get('active') and p['role'] == 'ops']

    def _invitations(self, request):
        return [i for i in self.store.all('invitation') if i['request_id'] == request['id']]

    def _invalidate(self, request, reason):
        for invitation in self._invitations(request):
            if invitation['status'] in {'pending', 'incomplete'}:
                invitation.update(status='invalidated', reason=reason)
                self.store.put('invitation', invitation)
                self._notify([invitation['recipient_id']], 'invitation_closed',
                             request_id=request['id'], reason=reason)

    def _deadline(self, request):
        return min(self._now() + timedelta(hours=24),
                   *(moment(a['starts_at']) for a in request['snapshots'].values()))

    def _invite(self, request, recipient):
        invitation = self._new('IV', 'invitation_id', request_id=request['id'],
            recipient_id=recipient, status='pending', created_at=self._now().isoformat(),
            expires_at=self._deadline(request).isoformat())
        self.store.put('invitation', invitation)
        self._notify([recipient], 'invitation', request_id=request['id'], invitation_id=invitation['id'])
        return invitation

    def _save_request(self, request):
        request['updated_at'] = self._now().isoformat()
        self.store.put('request', request)
        return request

    def _request_view(self, actor, request):
        person = self._actor(actor)
        if actor == request['owner_id'] or person['role'] == 'ops':
            return request
        invites = [i for i in self._invitations(request) if i['recipient_id'] == actor]
        if not invites:
            raise BeeBotError('FORBIDDEN', 'Yêu cầu không thuộc phạm vi của bạn.')
        return {k: request[k] for k in ('id', 'request_id', 'kind', 'status', 'assignment_id', 'created_at')}

    def _owner_or_ops(self, actor, request):
        person = self._actor(actor)
        if actor != request['owner_id'] and person['role'] != 'ops':
            raise BeeBotError('FORBIDDEN', 'Bạn không được sửa yêu cầu này.')
        return person

    def _check_slots(self, identifiers):
        for req in self.store.all('request'):
            if req['status'] not in TERMINAL and set(identifiers) & set(req['snapshots']):
                raise BeeBotError('DUPLICATE_REQUEST', 'Vị trí đã có yêu cầu đang mở: ' + req['id'])

    def _current_matches(self, request):
        for identifier, snapshot in request['snapshots'].items():
            try:
                actual = self.schedule.get_assignment(identifier)
            except BeeBotError as error:
                if error.code in {'ASSIGNMENT_NOT_FOUND', 'NOT_FOUND'}:
                    return False
                raise
            if any(actual.get(k) != snapshot.get(k) for k in SIGNATURE):
                return False
        return True

    def _updates(self, request, recipient):
        updates = {request['assignment_id']: recipient}
        if request['kind'] == 'swap':
            updates[request['target_assignment_id']] = request['owner_id']
        return updates

    def _eligible(self, request, recipient):
        self._recipient(recipient, request['owner_id'])
        updates = self._updates(request, recipient)
        assignments = self.schedule.list_assignments()
        resulting = [{**a, 'coach_id': updates.get(a['assignment_id'], a['coach_id'])}
                     for a in assignments]
        for identifier, coach in updates.items():
            desired = next((a for a in resulting if a['assignment_id'] == identifier), None)
            if not desired:
                raise BeeBotError('SCHEDULE_CHANGED', 'Vị trí không còn trên lịch.')
            for other in resulting:
                if other['assignment_id'] != identifier and other['coach_id'] == coach and overlaps(desired, other):
                    return False
            for reserved in self.store.all('request'):
                if reserved['id'] == request['id'] or reserved['status'] not in LOCKED:
                    continue
                for reserved_id, reserved_coach in reserved.get('planned_updates', {}).items():
                    if reserved_coach == coach and overlaps(desired, reserved['snapshots'][reserved_id]):
                        return False
        return True

    def get_my_assignments(self, actor_id):
        self._actor(actor_id)
        return [a for a in self.schedule.list_assignments() if a['coach_id'] == actor_id]

    def create_change_request(self, actor_id, kind, assignment_id, event_id, substitute_id=None,
                              target_assignment_id=None, sender_confirmed=False, sender_no_other_busy=False):
        def create():
            if kind not in {'replacement', 'leave', 'swap'}:
                raise BeeBotError('INVALID_KIND', 'Loại yêu cầu không hợp lệ.')
            if sender_confirmed is not True:
                raise BeeBotError('CONFIRMATION_REQUIRED', 'Người gửi cần xác nhận yêu cầu.')
            assignment = self.schedule.get_assignment(assignment_id)
            if assignment['coach_id'] != actor_id:
                raise BeeBotError('FORBIDDEN', 'Ca này không thuộc bạn.')
            snapshots = {assignment_id: assignment}
            recipient = substitute_id
            if kind == 'replacement' and not recipient:
                raise BeeBotError('RECIPIENT_REQUIRED', 'Cần chọn người nhận thay.')
            if kind == 'swap':
                if not target_assignment_id or target_assignment_id == assignment_id:
                    raise BeeBotError('TARGET_REQUIRED', 'Cần ca khác để hoán đổi.')
                if sender_no_other_busy is not True:
                    raise BeeBotError('CONFIRMATION_REQUIRED', 'Cần xác nhận không bận ngoài chương trình trong ca nhận.')
                target = self.schedule.get_assignment(target_assignment_id)
                recipient = target['coach_id']
                snapshots[target_assignment_id] = target
            if recipient:
                self._recipient(recipient, actor_id)
            if min(moment(a['starts_at']) for a in snapshots.values()) <= self._now():
                raise BeeBotError('SHIFT_STARTED', 'Ca đã bắt đầu, cần vận hành xử lý.')
            self._check_slots(snapshots)
            effective_kind = 'replacement' if kind == 'leave' and recipient else kind
            request = self._new('YC', 'request_id', owner_id=actor_id, kind=effective_kind,
                original_kind=kind, assignment_id=assignment_id, target_assignment_id=target_assignment_id,
                snapshots=snapshots, substitute_id=recipient, status='waiting_ops_approval' if effective_kind == 'leave' else 'waiting_confirmation',
                created_at=self._now().isoformat(), sender_confirmed=True,
                sender_no_other_busy=sender_no_other_busy is True, approval_by=None, reserved_for=None)
            if recipient:
                self._invite(request, recipient)
            self._save_request(request)
            self._notify([actor_id], 'request_created', request_id=request['id'], status=request['status'])
            if effective_kind == 'leave':
                self._notify(self._ops(), 'leave_needs_approval', request_id=request['id'])
            return request
        return self._mutation(actor_id, 'create_change_request', event_id, create)

    def get_request_status(self, actor_id, request_id):
        return self._request_view(actor_id, self._get('request', request_id))

    def list_my_requests(self, actor_id):
        person = self._actor(actor_id)
        return [r for r in self.store.all('request') if r['owner_id'] == actor_id or person['role'] == 'ops']

    def add_substitute(self, actor_id, request_id, substitute_id, event_id):
        def add():
            request = self._get('request', request_id)
            if request['owner_id'] != actor_id:
                raise BeeBotError('FORBIDDEN', 'Chỉ người gửi được bổ sung người thay.')
            if request['status'] not in {'waiting_ops_approval', 'waiting_confirmation', 'searching', 'needs_ops'}:
                raise BeeBotError('INVALID_STATE', 'Không thể đổi người thay ở trạng thái này.')
            if request['kind'] == 'swap':
                raise BeeBotError('INVALID_STATE', 'Hoán đổi cần tạo yêu cầu mới cho ca khác.')
            self._recipient(substitute_id, actor_id)
            if self._deadline(request) <= self._now():
                raise BeeBotError('SHIFT_STARTED', 'Ca đã bắt đầu.')
            self._invalidate(request, 'substitute_changed')
            request.update(kind='replacement', status='waiting_confirmation', substitute_id=substitute_id,
                           approval_by=None, approval_withdrawn=False)
            self._invite(request, substitute_id)
            self._notify(self._ops(), 'substitute_added', request_id=request_id, substitute_id=substitute_id)
            return self._save_request(request)
        return self._mutation(actor_id, 'add_substitute', event_id, add)

    def approve_leave_request(self, actor_id, request_id, event_id):
        def approve():
            self._actor(actor_id, ops=True)
            request = self._get('request', request_id)
            if request['kind'] != 'leave' or request['status'] != 'waiting_ops_approval':
                raise BeeBotError('INVALID_STATE', 'Yêu cầu không còn chờ chấp nhận nghỉ.')
            if self._deadline(request) <= self._now():
                raise BeeBotError('SHIFT_STARTED', 'Ca đã bắt đầu.')
            if not self._current_matches(request):
                request.update(status='needs_ops', reason='SCHEDULE_CHANGED')
                self._notify(self._ops(), 'schedule_changed', request_id=request_id)
                return self._save_request(request)
            request.update(status='searching', approval_by=actor_id, approved_at=self._now().isoformat())
            for person in self.schedule.list_people():
                if person.get('active') and person['role'] == 'labcoach' and person['person_id'] != request['owner_id']:
                    if self._eligible(request, person['person_id']):
                        self._invite(request, person['person_id'])
            if not self._invitations(request):
                request.update(status='needs_ops', reason='NO_CANDIDATES')
                self._notify(self._ops(), 'no_candidates', request_id=request_id)
            self._notify([request['owner_id']], 'leave_approved', request_id=request_id)
            return self._save_request(request)
        return self._mutation(actor_id, 'approve_leave_request', event_id, approve)

    def nominate_replacement(self, actor_id, request_id, substitute_id, event_id):
        def nominate():
            self._actor(actor_id, ops=True)
            request = self._get('request', request_id)
            if request['status'] in TERMINAL | LOCKED or request['kind'] == 'swap':
                raise BeeBotError('INVALID_STATE', 'Không thể bố trí ở trạng thái này.')
            if request['kind'] == 'leave' and not request.get('approval_by'):
                raise BeeBotError('APPROVAL_REQUIRED', 'Phải chấp nhận nghỉ trước khi mời người nhận.')
            self._recipient(substitute_id, request['owner_id'])
            if self._deadline(request) <= self._now():
                raise BeeBotError('SHIFT_STARTED', 'Ca đã bắt đầu.')
            self._invalidate(request, 'ops_nominated')
            request.update(substitute_id=substitute_id, status='waiting_confirmation')
            self._invite(request, substitute_id)
            return self._save_request(request)
        return self._mutation(actor_id, 'nominate_replacement', event_id, nominate)

    def get_my_invitations(self, actor_id):
        self._actor(actor_id)
        result = []
        for invitation in self.store.all('invitation'):
            if invitation['recipient_id'] != actor_id:
                continue
            view = dict(invitation)
            if view['status'] in {'pending', 'incomplete'} and self._now() >= moment(view['expires_at']):
                view['status'] = 'expired'
            request = self._get('request', view['request_id'])
            view['assignments'] = list(request['snapshots'].values())
            result.append(view)
        return result

    def respond_to_invitation(self, actor_id, invitation_id, accept, no_other_busy, event_id):
        def respond():
            invitation = self._get('invitation', invitation_id)
            if invitation['recipient_id'] != actor_id:
                raise BeeBotError('FORBIDDEN', 'Bạn không được xác nhận thay người khác.')
            request = self._get('request', invitation['request_id'])
            if invitation['status'] not in {'pending', 'incomplete'} or request['status'] in TERMINAL | LOCKED:
                raise BeeBotError('INVITATION_CLOSED', 'Lời mời đã đóng hoặc vị trí đã được giữ.')
            if self._now() >= moment(invitation['expires_at']):
                raise BeeBotError('INVITATION_EXPIRED', 'Lời mời đã hết hạn.')
            if accept is not True:
                invitation.update(status='declined', responded_at=self._now().isoformat())
                self.store.put('invitation', invitation)
                self._notify([request['owner_id']], 'invitation_declined', request_id=request['id'])
                self._exhausted(request)
                return self._save_request(request)
            if no_other_busy is not True:
                invitation.update(status='incomplete', accepted=True, no_other_busy=False)
                self.store.put('invitation', invitation)
                return {**request, 'reason': 'NO_OTHER_BUSY_CONFIRMATION_REQUIRED'}
            if not self._current_matches(request):
                request.update(status='needs_ops', reason='SCHEDULE_CHANGED')
                self._invalidate(request, 'schedule_changed')
                self._notify(self._ops() + [request['owner_id']], 'schedule_changed', request_id=request['id'])
                return self._save_request(request)
            if not self._eligible(request, actor_id):
                invitation.update(status='ineligible', reason='SCHEDULE_CONFLICT')
                self.store.put('invitation', invitation)
                self._notify([actor_id], 'schedule_conflict', request_id=request['id'])
                self._notify([request['owner_id']], 'recipient_ineligible', request_id=request['id'])
                self._exhausted(request)
                return {**self._save_request(request), 'reason': 'SCHEDULE_CONFLICT'}
            invitation.update(status='accepted', accepted=True, no_other_busy=True,
                              responded_at=self._now().isoformat())
            self.store.put('invitation', invitation)
            request.update(status='updating', reserved_for=actor_id,
                           planned_updates=self._updates(request, actor_id), write_started_at=self._now().isoformat())
            self._save_request(request)
            # Persist intent and chosen recipient before any external side effect.
            self._save_event(request)
            self.store.connection.commit()
            self.store.connection.execute('BEGIN IMMEDIATE')
            request = self._get('request', request['id'])
            if request['status'] == 'completed':
                return request
            return self._attempt_write(request)
        return self._mutation(actor_id, 'respond_to_invitation', event_id, respond)

    def _attempt_write(self, request):
        try:
            # Final full schedule/recipient check, after durable reservation.
            self._actor(request['owner_id'])
            self._actor(request['reserved_for'])
            if self._now() >= min(moment(a['starts_at']) for a in request['snapshots'].values()):
                request.update(status='write_failed', reason='SHIFT_STARTED')
                self._notify(self._ops(), 'write_failed', request_id=request['id'], reason='SHIFT_STARTED')
                return self._save_request(request)
            if not self._current_matches(request):
                raise BeeBotError('SCHEDULE_CHANGED', 'Lịch đã đổi ngay trước ghi.')
            if not self._eligible(request, request['reserved_for']):
                raise BeeBotError('SCHEDULE_CONFLICT', 'Lịch người nhận đã đổi ngay trước ghi.')
            self.schedule.apply_updates(request['planned_updates'], request['snapshots'])
        except BeeBotError as error:
            code = getattr(error, 'code', 'WRITE_FAILED')
            request['write_error'] = code
            if code == 'WRITE_UNCERTAIN':
                return self._reconcile(request)
            request.update(status='write_failed', reason=code)
            self._notify(self._ops(), 'write_failed', request_id=request['id'], reason=code)
            return self._save_request(request)
        except Exception:
            request['write_error'] = 'WRITE_UNCERTAIN'
            return self._reconcile(request)
        return self._reconcile(request)

    def _reconcile(self, request):
        if not request.get('planned_updates'):
            raise BeeBotError('INVALID_STATE', 'Yêu cầu chưa có bước ghi cần đối chiếu.')
        previous_status = request['status']
        previous_observed = request.get('observed_assignments')
        actual = {}
        try:
            actual = {identifier: self.schedule.get_assignment(identifier)
                      for identifier in request['planned_updates']}
            all_match = all(actual[identifier]['coach_id'] == coach and
                            all(actual[identifier].get(k) == request['snapshots'][identifier].get(k)
                                for k in SIGNATURE if k not in {'coach_id', 'revision'})
                            for identifier, coach in request['planned_updates'].items())
        except Exception:
            all_match = False
        request['observed_assignments'] = actual
        request['reconciled_at'] = self._now().isoformat()
        if all_match:
            first_completion = request['status'] != 'completed'
            request.update(status='completed', completed_at=self._now().isoformat())
            if first_completion:
                self._invalidate(request, 'completed')
                recipients = [request['owner_id'], request['reserved_for']] + self._ops()
                self._notify(recipients, 'request_completed', request_id=request['id'])
        else:
            request.update(status='reconciliation_required', reason='WRITE_NOT_VERIFIED')
            if previous_status != 'reconciliation_required' or previous_observed != actual:
                self._notify(self._ops(), 'reconciliation_required', request_id=request['id'])
        return self._save_request(request)

    def _exhausted(self, request):
        if not any(i['status'] in {'pending', 'incomplete'} and moment(i['expires_at']) > self._now()
                   for i in self._invitations(request)):
            request.update(status='needs_ops', reason='NO_ACTIVE_INVITATIONS')
            self._notify(self._ops(), 'no_active_invitations', request_id=request['id'])

    def cancel_request(self, actor_id, request_id, reason, event_id):
        def cancel():
            request = self._get('request', request_id)
            person = self._owner_or_ops(actor_id, request)
            if person['role'] == 'ops' and not str(reason or '').strip():
                raise BeeBotError('REASON_REQUIRED', 'Vận hành cần ghi lý do hủy.')
            if request['status'] in LOCKED:
                self._reconcile(request)
                return {**request, 'reason': 'RECONCILE_BEFORE_CANCELLATION'}
            if request['status'] in TERMINAL:
                raise BeeBotError('INVALID_STATE', 'Không thể hủy hoặc hoàn nguyên yêu cầu đã đóng.')
            self._invalidate(request, 'cancelled')
            request.update(status='cancelled', cancellation_reason=reason, cancelled_by=actor_id)
            self._notify([request['owner_id']] + self._ops(), 'request_cancelled', request_id=request_id)
            return self._save_request(request)
        return self._mutation(actor_id, 'cancel_request', event_id, cancel)

    def withdraw_leave_approval(self, actor_id, request_id, reason, event_id):
        def withdraw():
            self._actor(actor_id, ops=True)
            request = self._get('request', request_id)
            if not str(reason or '').strip():
                raise BeeBotError('REASON_REQUIRED', 'Cần lý do rút chấp nhận.')
            if request['kind'] != 'leave' or not request.get('approval_by'):
                raise BeeBotError('INVALID_STATE', 'Yêu cầu không có chấp nhận nghỉ đang hiệu lực.')
            if request['status'] in LOCKED:
                self._reconcile(request)
                return {**request, 'reason': 'RECONCILE_BEFORE_WITHDRAWAL'}
            if request['status'] in TERMINAL:
                raise BeeBotError('INVALID_STATE', 'Yêu cầu đã đóng, không thể hoàn nguyên lịch.')
            self._invalidate(request, 'approval_withdrawn')
            request.update(status='approval_withdrawn', approval_withdrawn=True, withdrawal_reason=reason)
            self._notify([request['owner_id']] + self._ops(), 'approval_withdrawn', request_id=request_id)
            return self._save_request(request)
        return self._mutation(actor_id, 'withdraw_leave_approval', event_id, withdraw)

    def reconcile_request(self, actor_id, request_id):
        self._actor(actor_id, ops=True)
        with self._lock:
            self.store.connection.execute('BEGIN IMMEDIATE')
            try:
                request = self._get('request', request_id)
                if request['status'] not in LOCKED | {'completed'}:
                    raise BeeBotError('INVALID_STATE', 'Không có lần ghi cần đối chiếu.')
                result = self._reconcile(request)
                self.store.connection.commit()
                return result
            except Exception:
                self.store.connection.rollback()
                raise

    def create_issue(self, actor_id, room, description, detected_at, event_id, photo=None, related_issue_id=None):
        def create():
            if not str(room or '').strip() or not str(description or '').strip():
                raise BeeBotError('ISSUE_DETAILS_REQUIRED', 'Cần phòng và mô tả sự cố.')
            moment(detected_at)
            if related_issue_id:
                self.get_issue_status(actor_id, related_issue_id)
            issue = self._new('IS', 'issue_id', owner_id=actor_id, room=room, description=description,
                detected_at=detected_at, photo=photo, related_issue_id=related_issue_id,
                status='open', created_at=self._now().isoformat())
            self.store.put('issue', issue)
            self._notify(self._ops(), 'issue_created', issue_id=issue['id'])
            self._notify([actor_id], 'issue_recorded', issue_id=issue['id'])
            return issue
        return self._mutation(actor_id, 'create_issue', event_id, create)

    def get_issue_status(self, actor_id, issue_id):
        person = self._actor(actor_id)
        issue = self._get('issue', issue_id)
        if person['role'] != 'ops' and issue['owner_id'] != actor_id:
            raise BeeBotError('FORBIDDEN', 'Sự cố không thuộc phạm vi của bạn.')
        return issue

    def update_issue(self, actor_id, issue_id, status, event_id, result=None):
        def update():
            person = self._actor(actor_id)
            issue = self._get('issue', issue_id)
            normalized = 'processing' if status == 'in_progress' else status
            if normalized not in {'processing', 'resolved', 'cancelled'}:
                raise BeeBotError('INVALID_STATUS', 'Trạng thái sự cố không hợp lệ.')
            owner_cancel = normalized == 'cancelled' and issue['status'] == 'open' and issue['owner_id'] == actor_id
            if person['role'] != 'ops' and not owner_cancel:
                raise BeeBotError('FORBIDDEN', 'Chỉ vận hành được xử lý sự cố; người gửi được hủy trước xử lý.')
            if issue['status'] in {'resolved', 'cancelled'}:
                raise BeeBotError('INVALID_STATE', 'Sự cố đã đóng; tái phát cần tạo bản ghi liên kết mới.')
            if (normalized == 'resolved' or (normalized == 'cancelled' and not owner_cancel)) and not str(result or '').strip():
                raise BeeBotError('RESULT_REQUIRED', 'Cần kết quả giải quyết hoặc lý do hủy.')
            issue.update(status=normalized, updated_at=self._now().isoformat(), updated_by=actor_id)
            if result:
                issue['result'] = result
            if normalized == 'resolved':
                issue.update(resolved_by=actor_id, resolved_at=self._now().isoformat())
            self.store.put('issue', issue)
            self._notify([issue['owner_id']], 'issue_updated', issue_id=issue_id, status=normalized)
            return issue
        return self._mutation(actor_id, 'update_issue', event_id, update)

    def get_my_notifications(self, actor_id):
        self._actor(actor_id)
        return [n for n in self.store.all('notification') if n['recipient_id'] == actor_id]

    def run_maintenance(self, actor_id):
        self._actor(actor_id, ops=True)
        with self._lock:
            self.store.connection.execute('BEGIN IMMEDIATE')
            try:
                now = self._now()
                expired, reconciled, alerts = [], [], []
                for invitation in self.store.all('invitation'):
                    if invitation['status'] in {'pending', 'incomplete'} and now >= moment(invitation['expires_at']):
                        invitation.update(status='expired')
                        self.store.put('invitation', invitation)
                        expired.append(invitation['id'])
                        self._notify([invitation['recipient_id']], 'invitation_expired', request_id=invitation['request_id'])
                for request in self.store.all('request'):
                    if request['status'] in {'updating', 'reconciliation_required'}:
                        self._reconcile(request)
                        reconciled.append(request['id'])
                    if request['status'] in TERMINAL:
                        continue
                    start = min(moment(a['starts_at']) for a in request['snapshots'].values())
                    if start <= now:
                        if request['status'] not in LOCKED:
                            self._invalidate(request, 'shift_started')
                            request.update(status='needs_ops', reason='SHIFT_STARTED')
                        if self.store.flag('start:' + request['id']):
                            self._notify(self._ops(), 'shift_started_unfilled', request_id=request['id'])
                            alerts.append(request['id'])
                    elif start - now <= timedelta(hours=2) and self.store.flag('urgent:' + request['id']):
                        self._notify(self._ops(), 'shift_within_two_hours', request_id=request['id'])
                        alerts.append(request['id'])
                    if request['status'] in {'searching', 'waiting_confirmation'}:
                        self._exhausted(request)
                    self._save_request(request)
                summaries = []
                local = now.astimezone(ZONE)
                for hour in (8, 16):
                    slot = f'{local.date()}T{hour:02}:00'
                    if local.hour >= hour and self.store.flag('summary:' + slot):
                        pending = [r['id'] for r in self.store.all('request') if r['status'] not in TERMINAL]
                        issues = [i['id'] for i in self.store.all('issue') if i['status'] not in {'resolved', 'cancelled'}]
                        self._notify(self._ops(), 'pending_summary', slot=slot, request_ids=pending, issue_ids=issues)
                        summaries.append(slot)
                self.store.connection.commit()
                return {'expired_invitations': expired, 'reconciled_requests': reconciled,
                        'alerted_requests': alerts, 'summary_slots': summaries}
            except Exception:
                self.store.connection.rollback()
                raise
