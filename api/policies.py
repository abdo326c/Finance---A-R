from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from models import get_db, PolicyDocument
from api.auth import get_current_user
import io

router = APIRouter()

@router.get("/")
async def get_documents(academic_year: str = None, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(PolicyDocument)
    if academic_year:
        query = query.filter(PolicyDocument.academic_year == academic_year)
    
    docs = query.order_by(PolicyDocument.uploaded_at.desc()).all()
    
    return [{
        "id": d.id,
        "title": d.title,
        "academic_year": d.academic_year,
        "file_name": d.file_name,
        "uploaded_by": d.uploaded_by,
        "uploaded_at": d.uploaded_at
    } for d in docs]

@router.get("/years")
async def get_document_years(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    years = db.query(PolicyDocument.academic_year).distinct().all()
    return [y[0] for y in years]

@router.post("/upload")
async def upload_document(
    title: str = Form(...),
    academic_year: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required to upload documents")
        
    contents = await file.read()
    
    new_doc = PolicyDocument(
        title=title,
        academic_year=academic_year,
        file_name=file.filename,
        file_data=contents,
        uploaded_by=current_user.username
    )
    
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    return {"message": "Document uploaded successfully", "id": new_doc.id}

@router.delete("/{doc_id}")
async def delete_document(doc_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required to delete documents")
        
    doc = db.query(PolicyDocument).filter(PolicyDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}

from fastapi.responses import Response

@router.get("/{doc_id}/download")
async def download_document(doc_id: int, current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(PolicyDocument).filter(PolicyDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return Response(
        content=doc.file_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{doc.file_name}"'}
    )
