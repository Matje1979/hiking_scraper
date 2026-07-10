from pydantic import BaseModel
from typing import List
from datetime import date

class NewHike(BaseModel):
    title: str
    hiking_club_id: int
    location_id: int
    exact_date: date
    link_to_detail_page: str
    guide: str
    description: str
    diff: int
    length: str
    height: str
    time_length: str
    price: str

class NewHikesList(BaseModel):
    hikes: List[NewHike] = []
