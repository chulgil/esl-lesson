"""함께 목표 — 친구 대화방 공유 체크리스트 + 주간 달성표 (docs/specs/shared-goals.md)."""

import pytest
from sqlalchemy import select

from app.models import SharedGoal
from app.services import chat as chat_service
from tests.test_chat import login, two_friends
from tests.test_daily_loop import _log_reviews
from tests.test_my_contents import login_as


@pytest.fixture(autouse=True)
def _fresh_caches():
    chat_service.reset_caches()
    yield
    chat_service.reset_caches()


# --- 조회: 대화 없음 --------------------------------------------------------------


async def test_get_goals_requires_friend_when_no_conversation(client, db_session):
    """대화가 아직 없으면 친구 검증만 거쳐 빈 응답 — 친구 아니면 404."""
    a = await login_as(client, db_session, "a@example.com")
    stranger = await login_as(client, db_session, "x@example.com")
    await login(client, db_session, a)

    res = await client.get(f"/api/chat/with/{stranger.id}/goals")
    assert res.status_code == 404


async def test_get_goals_empty_before_any_message(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    res = await client.get(f"/api/chat/with/{b.id}/goals")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["weekly"] == {"target": 300, "mine": 0, "theirs": 0}


# --- 체크리스트: 추가·조회·체크·해제·삭제 -----------------------------------------


async def test_add_check_appears_in_get_with_creator_name(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    created = await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "매일 10문제"})
    assert created.status_code == 201
    body = created.json()
    assert body["text"] == "매일 10문제"
    assert body["done"] is False
    assert body["done_by_name"] is None
    assert body["created_by_name"] == a.nickname

    listed = await client.get(f"/api/chat/with/{b.id}/goals")
    assert [i["text"] for i in listed.json()["items"]] == ["매일 10문제"]


async def test_check_and_uncheck_records_done_by(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (
        await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "영어로만 대화"})
    ).json()

    # 상대(b)가 체크 — done_by 는 체크한 사람
    await login(client, db_session, b)
    checked = await client.patch(f"/api/chat/goals/{created['id']}", json={"done": True})
    assert checked.status_code == 200
    assert checked.json()["done"] is True
    assert checked.json()["done_by_name"] == b.nickname

    unchecked = await client.patch(f"/api/chat/goals/{created['id']}", json={"done": False})
    assert unchecked.json()["done"] is False
    assert unchecked.json()["done_by_name"] is None


async def test_patch_text_edits_goal(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "초안"})).json()

    edited = await client.patch(f"/api/chat/goals/{created['id']}", json={"text": "수정된 목표"})
    assert edited.json()["text"] == "수정된 목표"


async def test_patch_rejects_blank_text(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "원본"})).json()

    res = await client.patch(f"/api/chat/goals/{created['id']}", json={"text": "   "})
    assert res.status_code == 422


async def test_delete_check_removes_it(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "지울 목표"})).json()

    res = await client.delete(f"/api/chat/goals/{created['id']}")
    assert res.status_code == 204

    listed = await client.get(f"/api/chat/with/{b.id}/goals")
    assert listed.json()["items"] == []


# --- 권한 -------------------------------------------------------------------------


async def test_non_participant_cannot_patch_or_delete(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    created = (await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "우리 목표"})).json()

    outsider = await login_as(client, db_session, "z@example.com")
    await login(client, db_session, outsider)

    patched = await client.patch(f"/api/chat/goals/{created['id']}", json={"done": True})
    assert patched.status_code == 403

    deleted = await client.delete(f"/api/chat/goals/{created['id']}")
    assert deleted.status_code == 403


async def test_add_goal_requires_friend(client, db_session):
    a = await login_as(client, db_session, "a2@example.com")
    stranger = await login_as(client, db_session, "x2@example.com")
    await login(client, db_session, a)

    res = await client.post(f"/api/chat/with/{stranger.id}/goals", json={"text": "목표"})
    assert res.status_code == 404


# --- 체크리스트 상한 ---------------------------------------------------------------


async def test_checklist_full_at_20_returns_422(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    for i in range(20):
        res = await client.post(f"/api/chat/with/{b.id}/goals", json={"text": f"목표 {i}"})
        assert res.status_code == 201

    over = await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "21번째"})
    assert over.status_code == 422
    assert over.json()["detail"] == "goals_full"


# --- 주간 달성표 -------------------------------------------------------------------


async def test_weekly_target_get_or_create_and_range_validation(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)

    default_view = (await client.get(f"/api/chat/with/{b.id}/goals")).json()
    assert default_view["weekly"]["target"] == 300

    updated = await client.patch(f"/api/chat/with/{b.id}/goals/weekly", json={"target_value": 500})
    assert updated.status_code == 200
    assert updated.json()["target"] == 500

    # 값이 유지됐는지 재조회로 확인 (get-or-create — 두 번째 호출은 기존 행 갱신)
    reloaded = (await client.get(f"/api/chat/with/{b.id}/goals")).json()
    assert reloaded["weekly"]["target"] == 500

    too_low = await client.patch(f"/api/chat/with/{b.id}/goals/weekly", json={"target_value": 5})
    assert too_low.status_code == 422
    too_high = await client.patch(
        f"/api/chat/with/{b.id}/goals/weekly", json={"target_value": 200_000}
    )
    assert too_high.status_code == 422


async def test_weekly_progress_counts_only_this_week_reviews(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    # 대화가 있어야 weekly 집계가 기본값이 아니라 실제 값을 낸다 — 대화 생성용 시드
    await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "seed"})

    # 이번 주 — a 3건, b 2건
    await _log_reviews(db_session, a.id, 3)
    await _log_reviews(db_session, b.id, 2)
    # 지난 주 — 집계에서 제외돼야 함 (KST 월요일 시작 기준으로 안전하게 8일 전)
    await _log_reviews(db_session, a.id, 5, days_ago=8)
    await db_session.commit()

    mine_view = (await client.get(f"/api/chat/with/{b.id}/goals")).json()
    assert mine_view["weekly"]["mine"] == 3
    assert mine_view["weekly"]["theirs"] == 2

    await login(client, db_session, b)
    theirs_view = (await client.get(f"/api/chat/with/{a.id}/goals")).json()
    assert theirs_view["weekly"]["mine"] == 2
    assert theirs_view["weekly"]["theirs"] == 3


# --- WS 동기화 ---------------------------------------------------------------------


async def test_mutations_push_goal_sync_to_both_participants(client, db_session, monkeypatch):
    a, b = await two_friends(client, db_session)
    pushed: list[tuple[int, dict]] = []

    async def fake_deliver(user_id, message):
        pushed.append((user_id, message))
        return True

    import app.api.chat as chat_api

    monkeypatch.setattr(chat_api.chat, "deliver_ws", fake_deliver)

    await login(client, db_session, a)
    created = (
        await client.post(f"/api/chat/with/{b.id}/goals", json={"text": "동기화 확인"})
    ).json()
    assert {uid for uid, _ in pushed} == {a.id, b.id}
    assert all(msg["t"] == "goal.sync" for _, msg in pushed)

    pushed.clear()
    await client.patch(f"/api/chat/goals/{created['id']}", json={"done": True})
    assert {uid for uid, _ in pushed} == {a.id, b.id}

    pushed.clear()
    await client.delete(f"/api/chat/goals/{created['id']}")
    assert {uid for uid, _ in pushed} == {a.id, b.id}

    pushed.clear()
    await client.patch(f"/api/chat/with/{b.id}/goals/weekly", json={"target_value": 400})
    assert {uid for uid, _ in pushed} == {a.id, b.id}


# --- weekly 행은 check 전용 경로에서 다뤄지지 않는다 -------------------------------


async def test_weekly_row_not_reachable_via_check_endpoints(client, db_session):
    a, b = await two_friends(client, db_session)
    await login(client, db_session, a)
    await client.patch(f"/api/chat/with/{b.id}/goals/weekly", json={"target_value": 400})

    row = (
        await db_session.execute(select(SharedGoal).where(SharedGoal.kind == "weekly_reviews"))
    ).scalar_one()

    patched = await client.patch(f"/api/chat/goals/{row.id}", json={"done": True})
    assert patched.status_code == 404

    deleted = await client.delete(f"/api/chat/goals/{row.id}")
    assert deleted.status_code == 404
