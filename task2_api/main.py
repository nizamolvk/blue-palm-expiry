from datetime import timedelta

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from task2_api.auth import require_api_key
from task2_api.config import TODAY
from task2_api.database import Base, make_engine, make_session_factory
from task2_api.models import Item
from task2_api.schemas import ExpiringItemOut, ItemCreate, ItemOut

BRANCHES = {"colombo": "Colombo", "dubai": "Dubai"}


def normalise_branch(branch: str | None) -> str | None:
    if branch is None:
        return None
    canonical = BRANCHES.get(branch.strip().casefold())
    if canonical is None:
        raise HTTPException(status_code=422, detail="branch must be Colombo or Dubai")
    return canonical


def create_app(engine=None) -> FastAPI:
    engine = make_engine() if engine is None else engine
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    app = FastAPI()
    app.state.session_factory = session_factory

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    router = APIRouter(dependencies=[Depends(require_api_key)])

    @router.get("/items", response_model=list[ItemOut])
    def list_items(branch: str | None = None, db: Session = Depends(get_db)):
        branch = normalise_branch(branch)
        query = db.query(Item)
        if branch:
            query = query.filter(Item.branch == branch)
        return query.order_by(Item.id).all()

    @router.get("/items/expiring", response_model=list[ExpiringItemOut])
    def list_expiring(
        days: int = Query(default=30, ge=0),
        branch: str | None = None,
        db: Session = Depends(get_db),
    ):
        branch = normalise_branch(branch)
        cutoff = TODAY + timedelta(days=days)
        query = db.query(Item).filter(Item.expiry_date.is_not(None), Item.expiry_date <= cutoff)
        if branch:
            query = query.filter(Item.branch == branch)
        rows = []
        for item in query.order_by(Item.expiry_date, Item.id).all():
            days_left = (item.expiry_date - TODAY).days
            status = "expired" if item.expiry_date < TODAY else "expiring"
            payload = ItemOut.model_validate(item).model_dump()
            payload["status"] = status
            payload["days_left"] = days_left
            rows.append(ExpiringItemOut(**payload))
        return rows

    @router.post("/items", response_model=ItemOut, status_code=201)
    def create_item(body: ItemCreate, db: Session = Depends(get_db)):
        existing = db.query(Item).filter(Item.item_id == body.item_id).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="item_id already exists")
        item = Item(
            item_id=body.item_id,
            branch=body.branch,
            item_type=body.item_type,
            item_name=body.item_name,
            responsible_email=body.responsible_email,
            expiry_date=body.expiry_date,
            annual_cost_usd=body.annual_cost_usd,
            notes=None,
            source_row=None,
            needs_review="no",
            review_reason=None,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    app.include_router(router)
    return app


app = create_app()
