from datetime import date
from typing import Annotated

from fastapi import Depends

from .deps import Search


def catalog_filters(creator: Search = '', action: Search = '', created_from: date | None = None,
                    created_to: date | None = None):
    from ..errors import Problem
    if created_from and created_to and created_from > created_to:
        raise Problem(422, 'INVALID_DATE_RANGE', '开始日期不能晚于结束日期')
    return {'creator': creator.strip(), 'action': action.strip(), 'created_from': created_from, 'created_to': created_to}


Filters = Annotated[dict, Depends(catalog_filters)]
