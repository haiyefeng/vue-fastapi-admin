from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.core.crud import CRUDBase
from app.models.todo import Review, ReviewPeriodType, ReviewStatus
from app.schemas.review import ReviewSaveIn


def _add_months(d: date, months: int) -> date:
    """按月数偏移，返回该月 1 号；用于计算月/季度周期的结束边界（下个周期起点减一天）"""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


class ReviewController(CRUDBase[Review, ReviewSaveIn, ReviewSaveIn]):
    def __init__(self):
        super().__init__(model=Review)

    @staticmethod
    def calc_period_range(period_type: ReviewPeriodType, anchor_date: date) -> Tuple[date, date]:
        """根据周期类型和锚点日期（周期内任意一天）计算周期起止日期"""
        if period_type == ReviewPeriodType.WEEK:
            start = anchor_date - timedelta(days=anchor_date.isoweekday() - 1)
            end = start + timedelta(days=6)
        elif period_type == ReviewPeriodType.MONTH:
            start = anchor_date.replace(day=1)
            end = _add_months(start, 1) - timedelta(days=1)
        elif period_type == ReviewPeriodType.QUARTER:
            quarter_start_month = ((anchor_date.month - 1) // 3) * 3 + 1
            start = anchor_date.replace(month=quarter_start_month, day=1)
            end = _add_months(start, 3) - timedelta(days=1)
        else:  # ReviewPeriodType.YEAR
            start = anchor_date.replace(month=1, day=1)
            end = anchor_date.replace(month=12, day=31)
        return start, end

    async def save_review(self, obj_in: ReviewSaveIn, user_id: int) -> Review:
        """同一用户同一周期类型同一起始日只保留一条记录：存在则覆盖更新，不存在则创建"""
        period_start, period_end = self.calc_period_range(obj_in.period_type, obj_in.anchor_date)
        review = await Review.filter(
            user_id=user_id, period_type=obj_in.period_type, period_start=period_start
        ).first()
        if review:
            await review.update_from_dict(
                {"period_end": period_end, "answers": obj_in.answers, "status": obj_in.status}
            ).save()
            return review
        return await Review.create(
            user_id=user_id,
            period_type=obj_in.period_type,
            period_start=period_start,
            period_end=period_end,
            answers=obj_in.answers,
            status=obj_in.status,
        )

    async def get_review_detail(
        self, period_type: ReviewPeriodType, anchor_date: date, user_id: int
    ) -> Optional[Review]:
        period_start, _ = self.calc_period_range(period_type, anchor_date)
        return await Review.filter(user_id=user_id, period_type=period_type, period_start=period_start).first()

    async def get_review_list(
        self, user_id: int, period_type: Optional[ReviewPeriodType] = None
    ) -> List[Review]:
        query = Review.filter(user_id=user_id)
        if period_type:
            query = query.filter(period_type=period_type)
        return await query.order_by("-period_start")


review_controller = ReviewController()
