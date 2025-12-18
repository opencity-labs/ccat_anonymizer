from typing import Set
from sqlalchemy.orm import Session
from cat.log import log
from .db import AllowedEntity, get_engine, Base
import os
import json

_allowedlist: Set[str] = set()
_engine = None

def init_allowedlist(db_path: str):
    global _allowedlist, _engine
    try:
        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        _engine = get_engine(db_path)
        Base.metadata.create_all(_engine)
        
        with Session(_engine) as session:
            entities = session.query(AllowedEntity).all()
            _allowedlist = {e.text for e in entities}
            
        log.info(json.dumps({
            "component": "ccat_anonymizer",
            "event": "initialization",
            "data": {
                "status": "success",
                "db_path": db_path,
                "loaded_entities": len(_allowedlist)
            }
        }))
    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "initialization",
            "data": {
                "status": "error",
                "error": str(e)
            }
        }))

def add_entity(text: str, entity_type: str):
    global _allowedlist, _engine
    if text in _allowedlist:
        return

    if _engine is None:
        # Try to initialize if not already (fallback, though init_allowedlist should be called)
        # But we need the path. 
        log.warning(json.dumps({
            "component": "ccat_anonymizer",
            "event": "allowedlist_error",
            "data": {
                "error": "Allowedlist engine not initialized, cannot add entity"
            }
        }))
        return

    try:
        with Session(_engine) as session:
            # Check if already exists (double check for race conditions or if set was out of sync)
            if not session.query(AllowedEntity).filter_by(text=text).first():
                entity = AllowedEntity(text=text, entity_type=entity_type)
                session.add(entity)
                session.commit()
                _allowedlist.add(text)
                
    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "allowedlist_error",
            "data": {
                "error": str(e)
            }
        }))

def is_allowed(text: str) -> bool:
    return text in _allowedlist
