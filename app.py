from flask import Flask, render_template, request, redirect, session, url_for
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import psycopg2
import os
from datetime import datetime, date
import pytz


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

DATABASE_URL = os.getenv("DATABASE_URL")

def obtener_conexion():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SET TIME ZONE 'America/Argentina/Buenos_Aires'")
    cur.close()
    return conn


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']

        conn = obtener_conexion()
        cur = conn.cursor()
        cur.execute("SELECT id, rol FROM usuarios_chipola WHERE usuario = %s AND password = %s", (usuario, contraseña))

        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['admin'] = (user[1] == 'admin')
            session['mayorista'] = (user[1] == 'mayorista')
            return redirect(url_for('cargar_producto'))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/editar_producto', methods=['POST'])
def editar_producto():
    if not session.get('admin'):
        return "Acceso denegado", 403

    id = request.form['id']
    descripcion = request.form['descripcion'].upper()
    memoria = request.form.get('memoria')
    condicion_bateria = request.form.get('condicion_bateria')
    estado = request.form['estado']
    precio_costo = request.form['precio_costo']
    precio_reventa = request.form['precio_reventa']
    precio_publico = request.form['precio_publico']
    stock = request.form['stock']
    foto = request.files.get('foto')

    conn = obtener_conexion()
    cur = conn.cursor()

    # Si hay foto nueva, la actualizamos
    if foto and foto.filename != '':
        from werkzeug.utils import secure_filename
        import os
        filename = secure_filename(foto.filename)
        path_foto = os.path.join('static/uploads', filename)
        foto.save(path_foto)
        foto_url = '/' + path_foto.replace('\\', '/')
        cur.execute("""
            UPDATE producto_chipola SET
                descripcion=%s,
                memoria=%s,
                condicion_bateria=%s,
                estado=%s,
                precio_costo=%s,
                precio_reventa=%s,
                precio_publico=%s,
                stock=%s,
                foto=%s
            WHERE id=%s
        """, (descripcion, memoria, condicion_bateria, estado,
              precio_costo, precio_reventa, precio_publico,
              stock, foto_url, id))
    else:
        # Si no se cambia la imagen
        cur.execute("""
            UPDATE producto_chipola SET
                descripcion=%s,
                memoria=%s,
                condicion_bateria=%s,
                estado=%s,
                precio_costo=%s,
                precio_reventa=%s,
                precio_publico=%s,
                stock=%s
            WHERE id=%s
        """, (descripcion, memoria, condicion_bateria, estado,
              precio_costo, precio_reventa, precio_publico, stock, id))

    conn.commit()
    cur.close()
    conn.close()
    return redirect('/cargar_producto')


@app.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    if not session.get('admin'):
        return "Acceso denegado"

    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM producto_chipola WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/cargar_producto')

def obtener_productos_filtrados(filtro=''):
    conn = obtener_conexion()
    cur = conn.cursor()

    if filtro:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria, precio_costo, precio_reventa, precio_publico, stock, vendido, estado
            FROM producto_chipola
            WHERE stock > 0 AND LOWER(descripcion) LIKE %s
        """, (f"%{filtro.lower()}%",))
    else:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria, precio_costo, precio_reventa, precio_publico, stock, vendido, estado 
            FROM producto_chipola
            WHERE stock > 0
        """)

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
            'precio_costo': p[5],
            'precio_reventa': p[6],
            'precio_publico': p[7],
            'stock': p[8],
            'vendido': p[9],
            'estado': p[10]
        })
    
    return productos


@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return "Acceso denegado"

    desde = request.args.get('desde') or '2000-01-01'
    hasta = request.args.get('hasta') or '2100-01-01'

    conn = obtener_conexion()
    cur = conn.cursor()

    # Montos por método de pago
    cur.execute("""
        SELECT metodo_pago, SUM(monto)
        FROM transacciones_chipola
        WHERE fecha BETWEEN %s AND %s
        GROUP BY metodo_pago
    """, (desde, hasta))
    pagos = cur.fetchall()

    # Montos por moneda
    cur.execute("""
        SELECT moneda, SUM(monto)
        FROM transacciones_chipola
        WHERE fecha BETWEEN %s AND %s
        GROUP BY moneda
    """, (desde, hasta))
    monedas = cur.fetchall()

    # Totales KPI
    cur.execute("""
        SELECT COALESCE(SUM(monto), 0) FROM transacciones_chipola
        WHERE fecha BETWEEN %s AND %s AND moneda = 'ARS'
    """, (desde, hasta))
    total_ars = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(monto), 0) FROM transacciones_chipola
        WHERE fecha BETWEEN %s AND %s AND moneda = 'USD'
    """, (desde, hasta))
    total_usd = cur.fetchone()[0]

    total_general = total_ars + total_usd

    cur.close()
    conn.close()

    return render_template("dashboard.html",
                           pagos=pagos,
                           monedas=monedas,
                           total_ars=round(total_ars, 2),
                           total_usd=round(total_usd, 2),
                           total_general=round(total_general, 2),
                           admin=True)


@app.route('/nuevo_deudor', methods=["POST"])
def nuevo_deudor():
    if not session.get('admin'):
        return "Acceso denegado"

    cliente_nombre = request.form.get("cliente_nombre")
    cliente_telefono = request.form.get("cliente_telefono")
    descripcion = request.form.get("descripcion")
    monto = request.form.get("monto")
    moneda = request.form.get("moneda", "ARS")
    fecha = request.form.get("fecha") or date.today()

    conn = obtener_conexion()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO deudores_chipola (cliente_nombre, cliente_telefono, descripcion, monto, fecha, pagado)
        VALUES (%s, %s, %s, %s, %s, FALSE)
    """, (cliente_nombre, cliente_telefono, descripcion, monto, fecha))

    conn.commit()
    cur.close()
    conn.close()

    # ✅ Guardar el mensaje de éxito
    session['mensaje'] = f"✅ Deudor {cliente_nombre} registrado correctamente."
    return redirect('/deudores')


@app.route('/marcar_pagado/<int:id>', methods=["POST"])
def marcar_pagado(id):
    if not session.get('admin'):
        return "Acceso denegado"

    metodo_pago = request.form.get('metodo_pago', 'Deuda saldada')
    moneda = request.form.get('moneda', 'ARS')
    monto = request.form.get('monto')

    conn = obtener_conexion()
    cur = conn.cursor()

    # Marcar como pagado
    cur.execute("UPDATE deudores_chipola SET pagado = TRUE WHERE id = %s", (id,))

    # Obtener nombre del cliente para mostrarlo en transacciones
    cur.execute("SELECT cliente_nombre FROM deudores_chipola WHERE id = %s", (id,))
    cliente = cur.fetchone()
    nombre_cliente = cliente[0] if cliente else "Cliente desconocido"

    # Registrar en transacciones
    fecha_actual = datetime.now(pytz.timezone("America/Argentina/Buenos_Aires"))

    cur.execute("""
        INSERT INTO transacciones_chipola (metodo_pago, moneda, monto, fecha, producto)
        VALUES (%s, %s, %s, %s, %s)
    """, (metodo_pago, moneda, monto, fecha_actual, f"Pago deuda - {nombre_cliente}"))

    conn.commit()
    cur.close()
    conn.close()

    return redirect('/deudores')




import psycopg2.extras

@app.route('/deudores')
def deudores():
    if not session.get('admin'):
        return "Acceso denegado"

    buscar = request.args.get('buscar', '')

    conn = obtener_conexion()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if buscar:
        cur.execute("""
            SELECT * FROM deudores_chipola 
            WHERE pagado = FALSE 
              AND (cliente_nombre ILIKE %s OR cliente_telefono ILIKE %s)
            ORDER BY fecha DESC
        """, (f'%{buscar}%', f'%{buscar}%'))
    else:
        cur.execute("""
            SELECT * FROM deudores_chipola 
            WHERE pagado = FALSE 
            ORDER BY fecha DESC
        """)
    deudores = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("deudores.html", deudores=deudores)



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
            precio_costo = float(request.form['precio_costo'])
            precio_reventa = float(request.form['precio_reventa'])
            precio_publico = float(request.form['precio_publico'])
            stock = int(request.form['stock'])
            estado = request.form['estado']
            categoria_id = int(request.form['categoria_id'])

            conn = obtener_conexion()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO producto_chipola 
                (foto, descripcion, memoria, condicion_bateria, precio_costo, 
                 precio_reventa, precio_publico, stock, vendido, estado, categoria_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
            """, (url_imagen, descripcion, memoria, condicion_bateria, precio_costo, 
                  precio_reventa, precio_publico, stock, estado, categoria_id))
            conn.commit()

        except Exception as e:
            if conn:
                conn.rollback()
            print("ERROR EN SQL -->", e)
            return f"Error detectado: {str(e)}"
        finally:
            if conn:
                cur.close()
                conn.close()

        return redirect('/cargar_producto')

    # GET: mostrar productos filtrados
    categoria_id = request.args.get('categoria')
    filtro = request.args.get('buscar', '').lower()
    productos = []

    conn = obtener_conexion()
    cur = conn.cursor()

    if categoria_id and filtro:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria,
                   precio_costo, precio_reventa, precio_publico,
                   stock, vendido, estado
            FROM producto_chipola
            WHERE stock > 0 AND categoria_id = %s AND LOWER(descripcion) LIKE %s
        """, (categoria_id, f"%{filtro}%"))
    elif categoria_id:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria,
                   precio_costo, precio_reventa, precio_publico,
                   stock, vendido, estado
            FROM producto_chipola
            WHERE stock > 0 AND categoria_id = %s
        """, (categoria_id,))
    elif filtro:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria,
                   precio_costo, precio_reventa, precio_publico,
                   stock, vendido, estado
            FROM producto_chipola
            WHERE stock > 0 AND LOWER(descripcion) LIKE %s
        """, (f"%{filtro}%",))
    else:
        cur.execute("""
            SELECT id, foto, descripcion, memoria, condicion_bateria,
                   precio_costo, precio_reventa, precio_publico,
                   stock, vendido, estado
            FROM producto_chipola
            WHERE stock > 0
        """)

    productos_db = cur.fetchall()
    cur.close()
    conn.close()

    for p in productos_db:
        productos.append({
            'id': p[0], 'foto': p[1], 'descripcion': p[2], 'memoria': p[3],
            'condicion_bateria': p[4], 'precio_costo': p[5], 'precio_reventa': p[6],
            'precio_publico': p[7], 'stock': p[8], 'vendido': p[9], 'estado': p[10]
        })

    return render_template('cargar_producto.html',
                           productos=productos,
                           filtro=filtro,
                           admin=session.get('admin'),
                           mayorista=session.get('mayorista'))




 
#---------------------------------------------------------------------------------------------------------
@app.route('/transacciones')
def transacciones():
    if not session.get('admin'):
        return "Acceso denegado"

    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    hoy = date.today()
    if not desde:
        desde = hoy.strftime('%Y-%m-%d')
    if not hasta:
        hasta = hoy.strftime('%Y-%m-%d')

    conn = obtener_conexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, fecha, metodo_pago, monto, moneda, producto
        FROM transacciones_chipola
        WHERE fecha::date BETWEEN %s AND %s
        ORDER BY fecha DESC
    """, (desde, hasta))
    datos = cur.fetchall()
    cur.close()
    conn.close()

    transacciones = []
    for t in datos:
        transacciones.append({
            'id': t[0],
            'fecha': t[1].strftime('%Y-%m-%d %H:%M'),
            'metodo_pago': t[2],
            'monto': t[3],
            'moneda': t[4],
            'producto': t[5] or "Pago deuda"
        })

    return render_template('transacciones.html', transacciones=transacciones, desde=desde, hasta=hasta)



@app.route('/registrar_venta', methods=['POST'])
def registrar_venta():
    if not session.get('admin'):
        return "Acceso denegado"

    producto_id = request.form['producto_id']
    metodo_pago = request.form['metodo_pago']
    monto = float(request.form['monto'])
    moneda = request.form['moneda']

    conn = obtener_conexion()
    cur = conn.cursor()

    try:
        # Obtener descripción del producto
        cur.execute("SELECT descripcion FROM producto_chipola WHERE id = %s", (producto_id,))
        producto_nombre = cur.fetchone()[0] if cur.rowcount > 0 else "Producto desconocido"

        # Obtener fecha y hora local en Argentina
        fecha_actual = datetime.now(pytz.timezone("America/Argentina/Buenos_Aires"))

# Insertar en transacciones con descripción
        cur.execute("""
            INSERT INTO transacciones_chipola (producto_id, metodo_pago, monto, moneda, fecha, producto)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (producto_id, metodo_pago, monto, moneda, fecha_actual, producto_nombre))

        # Actualizar stock del producto
        cur.execute("""
            UPDATE producto_chipola 
            SET stock = stock - 1 
            WHERE id = %s
        """, (producto_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error en venta: {str(e)}"
    finally:
        cur.close()
        conn.close()

    return redirect('/cargar_producto')


@app.route('/marcar_vendido/<int:id>', methods=['POST'])
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
