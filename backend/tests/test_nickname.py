"""닉네임 — 랜덤 초기값 + 변경 + 타인 표기(개인정보 비노출) (docs/specs/auth.md)."""

from app.models.friend import Friendship
from app.models.user import User
from app.services.nicknames import ADJECTIVES, NOUNS, random_nickname
from tests.test_study import login


def test_random_nickname_shape():
    nickname = random_nickname()
    assert any(nickname.startswith(a) for a in ADJECTIVES)
    assert any(n in nickname for n in NOUNS)
    assert nickname[-2:].isdigit()


async def test_new_user_gets_random_nickname_not_google_name(client, db_session):
    user = await login(client, db_session)
    res = await client.get("/api/me")
    body = res.json()
    assert body["nickname"] == user.nickname
    assert body["nickname"] != ""
    assert body["nickname"] != user.name  # 구글 이름을 초기값으로 쓰지 않는다


async def test_patch_nickname_normalizes_and_validates(client, db_session):
    await login(client, db_session)
    res = await client.patch("/api/me", json={"nickname": "  몰랑   테스터  "})
    assert res.status_code == 200
    assert res.json()["nickname"] == "몰랑 테스터"

    assert (await client.patch("/api/me", json={"nickname": "a"})).status_code == 422
    assert (await client.patch("/api/me", json={"nickname": "가" * 17})).status_code == 422


async def test_leaderboard_shows_nickname_not_name(client, db_session):
    me = await login(client, db_session)
    friend = User(
        google_sub="g-nick", email="nick@example.com", name="실명김철수", nickname="반짝브릭77"
    )
    db_session.add(friend)
    await db_session.flush()
    db_session.add(Friendship(requester_id=me.id, addressee_id=friend.id, status="accepted"))
    await db_session.commit()

    res = await client.get("/api/study/leaderboard")
    names = [r["name"] for r in res.json()["items"]]
    assert "반짝브릭77" in names
    assert "실명김철수" not in names
    assert me.nickname in names and me.name not in names


async def test_friends_list_shows_nickname(client, db_session):
    me = await login(client, db_session)
    other = User(
        google_sub="g-nick2", email="nick2@example.com", name="실명박영희", nickname="포근냥이31"
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(Friendship(requester_id=other.id, addressee_id=me.id, status="accepted"))
    await db_session.commit()

    res = await client.get("/api/friends")
    assert [f["name"] for f in res.json()["friends"]] == ["포근냥이31"]
