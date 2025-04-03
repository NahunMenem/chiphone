from flask import Flask, render_template, request, redirect, session, url_for
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import psycopg2
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")  # Clave secreta para sesiones

# Configuración Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

DATABASE_URL = os.getenv("DATABASE_URL")

def obtener_conexion():
    return psycopg2.connect(DATABASE_URL)

# ----------------- LOGIN -----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']

        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("SELECT password FROM usuarios_chipola WHERE usuario = %s", (usuario,))




        resultado = cur.fetchone()
        cur.close()
        conn.close()

        if resultado and resultado[0] == contraseña:
            session['admin'] = True
            return redirect('/cargar_producto')
        else:
            return render_template('login.html', error='Credenciales incorrectas')

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/cargar_producto')


# ----------------- PRODUCTOS -----------------

@app.route('/cargar_producto', methods=['GET', 'POST'])
def cargar_producto():
    if request.method == 'POST':
        if not session.get('admin'):
            return "Acceso denegado"

        conn = None
        try:
            foto = request.files['foto']
            if not foto:
                return "Error: No seleccionaste ninguna foto."

            upload_result = cloudinary.uploader.upload(foto)
            url_imagen = upload_result['secure_url']

            descripcion = request.form['descripcion']
            memoria = request.form['memoria']
            condicion_bateria = request.form['condicion_bateria']
            precio = float(request.form['precio'])
            estado = request.form['estado']

            conn = obtener_conexion()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO producto_chipola 
                (foto, descripcion, memoria, condicion_bateria, precio, vendido, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (url_imagen, descripcion, memoria, condicion_bateria, precio, False, estado))
            conn.commit()

        except Exception as e:
            if conn:
                conn.rollback()
            print("ERROR EN SQL -->", e)
            return f"Error detectado: {str(e)}"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        return redirect('/cargar_producto')

    # Filtro de búsqueda
    filtro = request.args.get('buscar', '')
    conn = obtener_conexion()
    cur = conn.cursor()

    if filtro:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria, precio, vendido, estado
            FROM producto_chipola
            WHERE LOWER(descripcion) LIKE %s
        """, (f"%{filtro.lower()}%",))
    else:
        cur.execute("SELECT id, foto, descripcion, memoria, condicion_bateria, precio, vendido, estado FROM producto_chipola")

    productos_db = cur.fetchall()
    cur.close()
    conn.close()

    productos = []
    for p in productos_db:
        productos.append({
            'id': p[0],
            'foto': p[1],
            'descripcion': p[2],
            'memoria': p[3],
            'condicion_bateria': p[4],
            'precio': p[5],
            'vendido': p[6],
            'estado': p[7]
        })

    return render_template('cargar_producto.html', productos=productos, filtro=filtro, admin=session.get('admin'))


@app.route('/marcar_vendido/<int:id>')
def marcar_vendido(id):
    if not session.get('admin'):
        return "Acceso denegado"
    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM producto_chipola WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/cargar_producto')


@app.route('/')
def index():
    return redirect('/cargar_producto')


if __name__ == '__main__':
    app.run(debug=True)
