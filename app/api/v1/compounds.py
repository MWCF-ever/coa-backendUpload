from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ...database import get_db
from ...models.compound import Compound
from ...schemas.compound import (
    CompoundCreate,
    CompoundUpdate,
    CompoundResponse,
    CompoundListResponse
)

router = APIRouter()


@router.get("/", response_model=CompoundListResponse)
async def get_compounds(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all compounds"""
    compounds = db.query(Compound).offset(skip).limit(limit).all()
    total = db.query(Compound).count()
    
    return CompoundListResponse(
        data=compounds,
        total=total
    )


@router.get("/{compound_id}", response_model=CompoundResponse)
async def get_compound(
    compound_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a specific compound by ID"""
    compound = db.query(Compound).filter(Compound.id == compound_id).first()
    if not compound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compound with id {compound_id} not found"
        )
    return compound


@router.post("/", response_model=CompoundResponse, status_code=status.HTTP_201_CREATED)
async def create_compound(
    compound: CompoundCreate,
    db: Session = Depends(get_db)
):
    """Create a new compound"""
    # Check if compound with same code already exists
    existing = db.query(Compound).filter(Compound.code == compound.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Compound with code {compound.code} already exists"
        )
    
    db_compound = Compound(**compound.dict())
    db.add(db_compound)
    db.commit()
    db.refresh(db_compound)
    
    return db_compound


@router.put("/{compound_id}", response_model=CompoundResponse)
async def update_compound(
    compound_id: UUID,
    compound_update: CompoundUpdate,
    db: Session = Depends(get_db)
):
    """Update a compound"""
    compound = db.query(Compound).filter(Compound.id == compound_id).first()
    if not compound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compound with id {compound_id} not found"
        )
    
    # Check if new code conflicts with existing compound
    if compound_update.code and compound_update.code != compound.code:
        existing = db.query(Compound).filter(Compound.code == compound_update.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Compound with code {compound_update.code} already exists"
            )
    
    # Update fields
    update_data = compound_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(compound, field, value)
    
    db.commit()
    db.refresh(compound)
    
    return compound


@router.delete("/{compound_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compound(
    compound_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a compound"""
    compound = db.query(Compound).filter(Compound.id == compound_id).first()
    if not compound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compound with id {compound_id} not found"
        )
    
    db.delete(compound)
    db.commit()
    
    return None


# Initialize default compounds on startup
@router.post("/init-defaults", response_model=List[CompoundResponse])
async def initialize_default_compounds(db: Session = Depends(get_db)):
    """Initialize default compounds (BGB-21447, BGB-16673, BGB-43395)"""
    default_compounds = [
        {"code": "BGB-21447", "name": "Compound BGB-21447", "description": "Default compound 1"},
        {"code": "BGB-16673", "name": "Compound BGB-16673", "description": "Default compound 2"},
        {"code": "BGB-43395", "name": "Compound BGB-43395", "description": "Default compound 3"}
    ]
    
    created = []
    for compound_data in default_compounds:
        existing = db.query(Compound).filter(Compound.code == compound_data["code"]).first()
        if not existing:
            compound = Compound(**compound_data)
            db.add(compound)
            created.append(compound)
    
    if created:
        db.commit()
        for compound in created:
            db.refresh(compound)
    
    return created