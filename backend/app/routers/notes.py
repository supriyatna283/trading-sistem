"""Symbol Notes API — GET and upsert per-symbol trader notes."""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.models.symbol_note import SymbolNote


router = APIRouter(prefix="/api/v1/notes", tags=["Symbol Notes"])


class KeyLevel(BaseModel):
    label: str   # e.g. "R1", "S1", "OB", "BOS"
    price: float


class NoteUpsert(BaseModel):
    content: Optional[str] = ""
    bias: Optional[str] = "NEUTRAL"   # BULLISH | BEARISH | NEUTRAL | WATCH | AVOID
    key_levels: Optional[List[KeyLevel]] = []


@router.get("/{symbol}")
async def get_note(symbol: str, db: Session = Depends(get_db)):
    """Return the note for a symbol, or an empty default if not found."""
    sym = symbol.upper()
    note = db.query(SymbolNote).filter(SymbolNote.symbol == sym).first()
    if not note:
        return {
            "note": {
                "symbol": sym,
                "content": "",
                "bias": "NEUTRAL",
                "key_levels": [],
                "updated_at": None,
            }
        }
    return {"note": note.to_dict()}


@router.put("/{symbol}")
async def upsert_note(symbol: str, data: NoteUpsert, db: Session = Depends(get_db)):
    """Create or update the note for a symbol."""
    sym = symbol.upper()
    note = db.query(SymbolNote).filter(SymbolNote.symbol == sym).first()

    levels_json = [kl.model_dump() for kl in (data.key_levels or [])]

    if note:
        note.content = data.content
        note.bias = data.bias
        note.key_levels = levels_json
        note.updated_at = datetime.utcnow()
    else:
        note = SymbolNote(
            symbol=sym,
            content=data.content,
            bias=data.bias,
            key_levels=levels_json,
        )
        db.add(note)

    db.commit()
    db.refresh(note)
    return {"note": note.to_dict()}


@router.get("")
async def list_notes(db: Session = Depends(get_db)):
    """List all symbols that have notes (for export)."""
    notes = db.query(SymbolNote).order_by(SymbolNote.updated_at.desc()).all()
    return {"notes": [n.to_dict() for n in notes]}


@router.delete("/{symbol}")
async def delete_note(symbol: str, db: Session = Depends(get_db)):
    """Delete the note for a symbol."""
    sym = symbol.upper()
    note = db.query(SymbolNote).filter(SymbolNote.symbol == sym).first()
    if note:
        db.delete(note)
        db.commit()
    return {"deleted": sym}
