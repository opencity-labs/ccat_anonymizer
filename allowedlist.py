from typing import Set
from sqlalchemy.orm import Session
from cat.log import log
from .db import AllowedEntity, EntitySource, get_engine, Base
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
            # Cleanup orphans: remove entities with no source
            subquery = session.query(EntitySource.entity_text)
            deleted_orphans = session.query(AllowedEntity).filter(AllowedEntity.text.notin_(subquery)).delete(synchronize_session=False)
            session.commit()

            entities = session.query(AllowedEntity).all()
            _allowedlist = {e.text for e in entities}
            
        log.info(json.dumps({
            "component": "ccat_anonymizer",
            "event": "initialization",
            "data": {
                "status": "success",
                "db_path": db_path,
                "loaded_entities": len(_allowedlist),
                "cleaned_orphans": deleted_orphans
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

def add_entity(text: str, entity_type: str, source: str = "unknown"):
    global _allowedlist, _engine
    if text in _allowedlist:
        # Even if in allowedlist, we might need to add a new source
        pass

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
            # Check if entity exists
            entity = session.query(AllowedEntity).filter_by(text=text).first()
            if not entity:
                entity = AllowedEntity(text=text, entity_type=entity_type)
                session.add(entity)
            
            # Check if source exists for this entity
            source_exists = session.query(EntitySource).filter_by(entity_text=text, source=source).first()
            
            if not source_exists:
                new_source = EntitySource(entity_text=text, source=source)
                session.add(new_source)
                
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

def remove_source(source: str):
    global _allowedlist, _engine
    if _engine is None:
        return

    try:
        with Session(_engine) as session:
            # 1. Delete all EntitySource entries with this source
            session.query(EntitySource).filter_by(source=source).delete()
            
            # 2. Find entities that have no sources left
            subquery = session.query(EntitySource.entity_text).distinct()
            entities_to_remove = session.query(AllowedEntity).filter(AllowedEntity.text.notin_(subquery)).all()
            
            for ent in entities_to_remove:
                if ent.text in _allowedlist:
                    _allowedlist.remove(ent.text)
                session.delete(ent)
            
            session.commit()
            
            log.info(json.dumps({
                "component": "ccat_anonymizer",
                "event": "source_removed",
                "data": {
                    "source": source,
                    "removed_entities": len(entities_to_remove)
                }
            }))

    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "remove_source_error",
            "data": {
                "error": str(e)
            }
        }))

def is_allowed(text: str) -> bool:
    return text in _allowedlist
