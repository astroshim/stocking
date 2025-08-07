import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import or_, asc
from app.db.models.comment import Comment
from app.db.repositories.comment_repository import CommentRepository
from app.utils.transaction_manager import TransactionManager


class CommentService:
    def __init__(self, comment_repository: CommentRepository):
        self.repository = comment_repository
        self.logger = logging.getLogger(__name__)

    def create_comment(self, user_id: str, commentable_id: str, commentable_type: str,
                       content: str, parent_id: Optional[str] = None, is_question: bool = True) -> Comment:
        """코멘트 생성 (부모 코멘트 ID 옵션)"""
        with TransactionManager.transaction(self.repository.session):
            comment = Comment(
                user_id=user_id,
                commentable_id=commentable_id,
                commentable_type=commentable_type,
                content=content,
                is_question=is_question
            )

            if parent_id:
                parent = self.repository.get_by_id(parent_id)
                if parent:
                    # 부모 ID를 ancestry에 추가
                    comment.ancestry = f"{parent.ancestry}/{parent.id}" if parent.ancestry else parent.id
                    comment.ancestry_depth = parent.ancestry_depth + 1

                    # 부모 코멘트의 children_count 증가
                    parent.children_count += 1

                    # 답변인 경우
                    if not is_question:
                        # 실제로는 사용자 정보를 가져와야 함
                        # TODO: 챌린지 주인인지 확인하는 로직
                        comment.answer_name = "챌린지 운영자"

            self.repository.add(comment)
            return comment

    def get_comment_by_id(self, comment_id: str) -> Optional[Comment]:
        """코멘트 단일 조회"""
        return self.repository.get_by_id(comment_id)

    def update_comment(self, id: str, user_id: str, content: str) -> Optional[Comment]:
        """코멘트 업데이트"""
        with TransactionManager.transaction(self.repository.session):
            comment = self.repository.get_by_id(id)
            if comment and comment.user_id == user_id:
                comment.content = content
                comment.updated_at = datetime.now()
                return comment
            return None

    def get_comment_with_replies(self, comment_id: str, include_replies: bool = False) -> Optional[Dict[str, Any]]:
        """
        코멘트 및 해당 코멘트의 대댓글을 포함하여 조회합니다.

        Args:
            comment_id: 조회할 코멘트 ID
            include_replies: 대댓글 포함 여부

        Returns:
            Optional[Dict[str, Any]]: 코멘트 정보와, 요청 시 대댓글을 포함한 딕셔너리
        """
        comment = self.get_comment_by_id(comment_id)

        if not comment:
            return None

        # 기본 코멘트 정보 변환
        comment_dict = {
            "id": comment.id,
            "user_id": comment.user_id,
            "commentable_type": comment.commentable_type,
            "commentable_id": comment.commentable_id,
            "content": comment.content,
            "ancestry": comment.ancestry,
            "ancestry_depth": comment.ancestry_depth,
            "children_count": comment.children_count,
            "is_question": comment.is_question,
            "answer_name": comment.answer_name,
            "created_at": int(comment.created_at.timestamp()),
            "updated_at": int(comment.updated_at.timestamp())
        }

        if include_replies and comment.children_count > 0:
            replies = self.repository.session.query(Comment).filter(
                Comment.commentable_id == comment.commentable_id,
                Comment.commentable_type == comment.commentable_type,
                Comment.ancestry.like(f"%{comment.id}%")
            ).order_by(asc(Comment.ancestry_depth), asc(Comment.created_at)).all()

            logging.debug(f"대댓글 수: {len(replies)}")

            # 대댓글 정보 변환
            replies_list = []
            for reply in replies:
                reply_dict = {
                    "id": reply.id,
                    "user_id": reply.user_id,
                    "commentable_type": reply.commentable_type,
                    "commentable_id": reply.commentable_id,
                    "content": reply.content,
                    "ancestry": reply.ancestry,
                    "ancestry_depth": reply.ancestry_depth,
                    "children_count": reply.children_count,
                    "is_question": reply.is_question,
                    "answer_name": reply.answer_name,
                    "created_at": int(reply.created_at.timestamp()),
                    "updated_at": int(reply.updated_at.timestamp())
                }

                replies_list.append(reply_dict)

            comment_dict["replies"] = replies_list

        return comment_dict

    def get_comment_tree(self, commentable_type: str, commentable_id: str) -> List[Dict[str, Any]]:
        """코멘트 트리 구조로 가져오기"""
        # 최상위 코멘트만 가져옴 (ancestry가 없는)
        root_comments = self.repository.session.query(Comment).filter(
            Comment.commentable_id == commentable_id,
            Comment.commentable_type == commentable_type,
            Comment.ancestry.is_(None)
        ).order_by(Comment.created_at.desc()).all()

        result = []
        for comment in root_comments:
            # 기본 코멘트 정보
            comment_dict = {
                "id": comment.id,
                "user_id": comment.user_id,
                "commentable_type": comment.commentable_type,
                "commentable_id": comment.commentable_id,
                "content": comment.content,
                "ancestry": comment.ancestry,
                "ancestry_depth": comment.ancestry_depth,
                "children_count": comment.children_count,
                "is_question": comment.is_question,
                "answer_name": comment.answer_name,
                "created_at": int(comment.created_at.timestamp()),
                "updated_at": int(comment.updated_at.timestamp()),
                "children": []
            }

            # 자식 코멘트 가져오기 (lazy loading 방식)
            if comment.children_count > 0:
                children = self.repository.session.query(Comment).filter(
                    Comment.ancestry.like(f"{comment.id}%")
                ).order_by(Comment.created_at).all()

                # 자식 코멘트 정리
                for child in children:
                    child_dict = {
                        "id": child.id,
                        "user_id": child.user_id,
                        "commentable_type": child.commentable_type,
                        "commentable_id": child.commentable_id,
                        "content": child.content,
                        "ancestry": child.ancestry,
                        "ancestry_depth": child.ancestry_depth,
                        "children_count": child.children_count,
                        "is_question": child.is_question,
                        "answer_name": child.answer_name,
                        "created_at": int(child.created_at.timestamp()),
                        "updated_at": int(child.updated_at.timestamp())
                    }
                    comment_dict["children"].append(child_dict)

            result.append(comment_dict)

        return result

    def get_comment_tree_deep(self, commentable_type: str, commentable_id: str) -> List[Dict[str, Any]]:
        """코멘트 트리 구조로 가져오기"""
        # 최상위 코멘트만 가져옴 (ancestry가 없는)
        root_comments = self.repository.session.query(Comment).filter(
            Comment.commentable_id == commentable_id,
            Comment.commentable_type == commentable_type,
            Comment.ancestry.is_(None)
        ).order_by(Comment.created_at.desc()).all()

        # 모든 자손 코멘트를 한 번에 가져옴 (성능 개선을 위해)
        all_children = []
        if root_comments:
            root_ids = [comment.id for comment in root_comments]
            ancestry_filter = []
            for root_id in root_ids:
                ancestry_filter.append(Comment.ancestry.like(f"{root_id}%"))

            if ancestry_filter:
                all_children = self.repository.session.query(Comment).filter(
                    or_(*ancestry_filter)
                ).order_by(Comment.created_at).all()

        # 부모 ID를 키로 하는 자식 코멘트 맵 생성
        child_map = {}
        for child in all_children:
            if child.ancestry:
                parts = child.ancestry.split('/')
                parent_id = parts[-1]
                if parent_id not in child_map:
                    child_map[parent_id] = []
                child_map[parent_id].append(child)

        # 재귀적으로 트리 구성
        def build_comment_tree(comment):
            comment_dict = {
                "id": comment.id,
                "user_id": comment.user_id,
                "commentable_type": comment.commentable_type,
                "commentable_id": comment.commentable_id,
                "content": comment.content,
                "ancestry": comment.ancestry,
                "ancestry_depth": comment.ancestry_depth,
                "children_count": comment.children_count,
                "is_question": comment.is_question,
                "answer_name": comment.answer_name,
                "created_at": int(comment.created_at.timestamp()),
                "updated_at": int(comment.updated_at.timestamp()),
                "children": []
            }

            # 자식 코멘트 추가
            children = child_map.get(comment.id, [])
            for child in children:
                comment_dict["children"].append(build_comment_tree(child))

            return comment_dict

        # 루트 코멘트부터 트리 구성
        result = []
        for comment in root_comments:
            result.append(build_comment_tree(comment))

        return result

    def list_comments(self, filters: Dict[str, Any] = None):
        """필터를 사용한 코멘트 목록 조회"""
        return self.repository.list_comments(filters)

    def delete_comment(self, user_id: str, comment_id: str) -> bool:
        """코멘트 삭제 (하위 코멘트도 모두 삭제)"""
        with TransactionManager.transaction(self.repository.session):
            comment = self.repository.get_by_id(comment_id)
            if not comment or comment.user_id != user_id:
                return False

            # 부모 코멘트가 있는 경우 children_count 감소
            if comment.ancestry:
                ancestry_parts = comment.ancestry.split("/")
                parent_id = ancestry_parts[-1]
                parent = self.repository.get_by_id(parent_id)
                if parent:
                    parent.children_count -= (1 + comment.children_count)

            # 하위 코멘트 모두 검색
            child_comments = self.repository.session.query(Comment).filter(
                Comment.commentable_id == comment.commentable_id,
                Comment.commentable_type == comment.commentable_type,
                or_(
                    Comment.ancestry == comment.id,
                    Comment.ancestry.like(f"{comment.id}/%")
                )
            ).all()

            self.logger.debug(f"삭제할 자식 코멘트 수: {len(child_comments)}")

            # 자식 코멘트 ID 목록 확인
            child_ids = [c.id for c in child_comments]
            self.logger.debug(f"삭제할 자식 코멘트 ID: {child_ids}")

            # 하위 코멘트 삭제
            if child_comments:
                self.repository.session.query(Comment).filter(
                    Comment.id.in_(child_ids)
                ).delete(synchronize_session=False)

            # 자신 삭제
            self.repository.delete(comment)
            return True
