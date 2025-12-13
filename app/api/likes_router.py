import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter(prefix="/api/likes", tags=["Likes"])

LIKES_FILE = Path("data/likes.json")


class LikeRequest(BaseModel):
    post_id: int
    liked: bool


class LikeResponse(BaseModel):
    user_id: int
    post_id: int
    liked: bool


def read_likes() -> List[Dict[str, Any]]:
    """Чтение лайков из JSON файла."""
    try:
        if not LIKES_FILE.exists():
            return []
        with open(LIKES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка чтения файла лайков: {e}")
        return []


def write_likes(likes: List[Dict[str, Any]]) -> None:
    """Запись лайков в JSON файл."""
    try:
        with open(LIKES_FILE, "w", encoding="utf-8") as f:
            json.dump(likes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка записи в файл лайков: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save like",
        )


@router.post("/toggle", response_model=LikeResponse)
async def toggle_like(
    like_request: LikeRequest, current_user: User = Depends(get_current_user)
):
    """Переключение лайка для поста."""
    likes = read_likes()

    like_index = next(
        (
            i
            for i, like in enumerate(likes)
            if like["user_id"] == current_user.id
            and like["post_id"] == like_request.post_id
        ),
        None,
    )

    if like_index is not None:
        likes[like_index]["liked"] = not likes[like_index]["liked"]
        if not likes[like_index]["liked"]:
            likes.pop(like_index)
    else:
        if like_request.liked:
            likes.append(
                {
                    "user_id": current_user.id,
                    "post_id": like_request.post_id,
                    "liked": True,
                }
            )

    write_likes(likes)

    current_like = next(
        (
            like
            for like in likes
            if like["user_id"] == current_user.id
            and like["post_id"] == like_request.post_id
        ),
        None,
    )

    is_liked = current_like["liked"] if current_like else False

    return {
        "user_id": current_user.id,
        "post_id": like_request.post_id,
        "liked": is_liked,
    }


@router.get("/user/{user_id}", response_model=List[Dict[str, Any]])
async def get_user_likes(user_id: int):
    """Получить все лайки конкретного пользователя."""
    likes = read_likes()
    return [like for like in likes if like["user_id"] == user_id and like["liked"]]


@router.get("/post/{post_id}", response_model=List[Dict[str, Any]])
async def get_post_likes(post_id: int):
    """Получить все лайки конкретного поста."""
    likes = read_likes()
    return [like for like in likes if like["post_id"] == post_id and like["liked"]]


@router.get("/user/{user_id}/post/{post_id}", response_model=bool)
async def is_post_liked_by_user(user_id: int, post_id: int):
    """Проверить, лайкнул ли пользователь конкретный пост."""
    likes = read_likes()
    return any(
        like["user_id"] == user_id and like["post_id"] == post_id and like["liked"]
        for like in likes
    )
