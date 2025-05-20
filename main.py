import logging
import re
from typing import Optional
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from sqlalchemy import Column, Integer, String, Date, create_engine, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from sqlalchemy import ForeignKey
from fastapi import Query

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- DB setup ---
DATABASE_URL = "sqlite:///./bbdd.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Users:
    def __init__(self, nombre: str, email: str, telefono: str, direccion: str):
        self.nombre = nombre
        self.email = email
        self.telefono = telefono
        self.direccion = direccion


class Animal:
    def __init__(self, nombre: str, edad: int, tipo: str):
        self.nombre = nombre
        self.edad = edad
        self.tipo = tipo
        self.adoptado = False


class Perro(Animal):
    def __init__(self, nombre: str, edad: int, raza: str):
        super().__init__(nombre, edad, tipo = "perro")
        self.raza = raza


class Gato(Animal):
    def __init__(self, nombre: str, edad: int, color: str):
        super().__init__(nombre, edad, tipo = "gato")
        self.color = color


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True, index=True)


class AnimalDB(Base):
    __tablename__ = "animals"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    edad = Column(Integer)
    tipo = Column(String)
    adoptado = Column(Boolean, default=False)


class AdoptionDB(Base):
    __tablename__ = "adoptions"

    fecha = Column(Date)
    # animal_id = Column(Integer, primary_key=True, index=True)
    animal_id = Column(Integer, ForeignKey("animals.id"), primary_key=True, index=True)
    # user_id = Column(Integer, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

Base.metadata.create_all(bind=engine)


# --- Pydantic model ---

class UsersSchema(BaseModel):
    nombre: str = Field(..., description="Nombre del usuario que quiere adoptar")
    email: str = Field(..., description="Email del usuario que quiere adoptar")
    telefono: int = Field(None, ge=0, description="Teléfono")
    direccion: str = Field(..., description="Dirección de residencia")

    @field_validator("nombre")
    def lenght_name(cls, value):
        if len(value) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        return value

    @field_validator("telefono")
    def lenght_name(cls, value):
        if len(str(value)) != 9:
            raise ValueError("El nombre debe tener 9 dígitos")
        return value

    @field_validator("email")
    def validar_email(cls, valor):
        patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(patron, valor):
            raise ValueError("El correo no está bien formado")
        return valor


class AnimalSchema(BaseModel):
    nombre: str = Field(..., description="Nombre del animal")
    edad: int = Field(None, ge=0, description="Edad no negativa")
    tipo: str = Field(..., description="Tipo (perro o gato)")

    @field_validator("nombre")
    def lenght_name_1(cls, value):
        if len(value) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        return value

    @field_validator("tipo")
    def validar_tipo(cls, value):
        if value not in ["perro", "gato"]:
            raise ValueError("El tipo debe ser 'perro' o 'gato'")
        return value
    

class AdoptionSchema(BaseModel):
    nombre_animal: str = Field(..., description="Nombre del animal que quiere adoptar")
    nombre_user: str = Field(..., description="Nombre del usuario que quiere adoptar")

# --- FastAPI setup ---
app = FastAPI(
    title="Mi primera API con FastAPI",
    description="Una API de ejemplo con base de datos SQLite.",
    version="1.0.0"
)

@app.post("/users/")
def create_user(user: UsersSchema):
    logger.info(f"📥 Registro de usuario recibido: {user}")
    
    db = SessionLocal()
    existing = db.query(UserDB).filter(UserDB.email == user.email).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="El usuario ya está registrado")

    user_db = UserDB(nombre=user.nombre, email=user.email)
    db.add(user_db)
    db.commit()
    db.refresh(user_db)
    db.close()
    logger.info(f"✅ Usuario guardado en DB: {user_db.nombre}")
    return {
        "msg": "Usuario registrado correctamente",
        "usuario": {
            "id": user_db.id,
            "nombre": user_db.nombre,
            "email": user_db.email,
        }
    }


@app.post("/animals/")
def create_animal(animal: AnimalSchema):
    logger.info(f"📥 Registro de usuario recibido: {animal}")
    
    db = SessionLocal()
    existing = db.query(AnimalDB).filter(AnimalDB.nombre == animal.nombre).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="El animal ya está registrado")

    animal_db = AnimalDB(nombre=animal.nombre, edad=animal.edad, tipo=animal.tipo)
    db.add(animal_db)
    db.commit()
    db.refresh(animal_db)
    db.close()
    logger.info(f"✅ Animal guardado en DB: {animal_db.nombre}")
    return {
        "msg": "Animal registrado correctamente",
        "animal": {
            "id": animal_db.id,
            "nombre": animal_db.nombre,
            "edad": animal_db.edad
        }
    }


@app.get("/disponibles")
def get_available_animals(tipo: str = Query(None, description="Filtrar por tipo de animal ('perro' o 'gato')")):
    db = SessionLocal()
    if tipo:
        animals = db.query(AnimalDB).filter(AnimalDB.adoptado == False, AnimalDB.tipo == tipo).all()
    else:
        animals = db.query(AnimalDB).filter(AnimalDB.adoptado == False).all()
    db.close()

    return {
        "msg": "Animales disponibles para adopción:",
        "animales": [
            {"nombre": animal.nombre, "edad": animal.edad, "tipo": animal.tipo} for animal in animals
        ]
    }


@app.post("/adopcion/random/")
def adopt_animal(user_name: str, tipo: str = Query(None, description="Filtrar por tipo de animal ('perro' o 'gato')")):
    
    db = SessionLocal()
    # si el usuario existe
    user_adopt = db.query(UserDB).filter(UserDB.nombre == user_name).first()
    if not user_adopt:
        db.close()
        raise HTTPException(status_code=400, detail="El usuario no está registrado")
    user_id = user_adopt.id
    if tipo:
        animal_adopt = db.query(AnimalDB).filter(AnimalDB.adoptado == False, AnimalDB.tipo == tipo).order_by(AnimalDB.edad.desc()).first()
    else:
        animal_adopt = db.query(AnimalDB).filter(AnimalDB.adoptado == False).order_by(AnimalDB.edad.desc()).first()
    if not animal_adopt:
        db.close()
        raise HTTPException(status_code=400, detail="No hay animales disponibles para adopción")
    animal_id = animal_adopt.id
    animal_name = animal_adopt.nombre

    # registramos la adopción
    adoption_db = AdoptionDB(fecha=date.today(), animal_id=animal_id, user_id=user_id)
    db.add(adoption_db)

    #modificamos el animal para que no esté disponible
    animal_db = db.query(AnimalDB).filter(AnimalDB.id == animal_id).first()
    animal_db.adoptado = True

    db.commit()

    return {
        "msg": "Adopción registrada correctamente",
        "adopcion": {
            "animal_name": animal_name,
            "user_name": user_name,
        }
    }


@app.post("/adopcion/")
def adopt_animal(user_name: str, animal_name: str):
    
    db = SessionLocal()
    # si el usuario existe
    user_adopt = db.query(UserDB).filter(UserDB.nombre == user_name).first()
    if not user_adopt:
        db.close()
        raise HTTPException(status_code=400, detail="El usuario no está registrado")
    user_id = user_adopt.id
    # si el animal existe
    animal_adopt = db.query(AnimalDB).filter(AnimalDB.nombre == animal_name).first()
    if not animal_adopt:
        db.close()
        raise HTTPException(status_code=400, detail="El animal no está registrado")
    animal_id = animal_adopt.id
    animal_available = db.query(AnimalDB).filter(AnimalDB.id == animal_id, AnimalDB.adoptado == False).first()
    if not animal_available:
        db.close()
        raise HTTPException(status_code=400, detail="El animal no está disponible para adopción")
    db.close()

    # registramos la adopción
    adoption_db = AdoptionDB(fecha=date.today(), animal_id=animal_id, user_id=user_id)
    db.add(adoption_db)

    #modificamos el animal para que no esté disponible
    animal_db = db.query(AnimalDB).filter(AnimalDB.id == animal_id).first()
    animal_db.adoptado = True

    db.commit()

    return {
        "msg": "Adopción registrada correctamente",
        "adopcion": {
            "animal_name": animal_name,
            "user_name": user_name,
        }
    }


