from app import db

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    foto = db.Column(db.String(250))
    descripcion = db.Column(db.String(250))
    memoria = db.Column(db.String(50))
    condicion_bateria = db.Column(db.String(50))
    precio = db.Column(db.Float)
    vendido = db.Column(db.Boolean, default=False)
