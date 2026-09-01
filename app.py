import hashlib
import io
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
DB_NAME = "neumaticos_stock.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medida TEXT NOT NULL,
            dot TEXT NOT NULL,
            anio_dot INTEGER NOT NULL,
            ubicacion TEXT NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL,
            medida TEXT NOT NULL,
            dot TEXT NOT NULL,
            ubicacion TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            ref_documental TEXT NOT NULL,
            usuario TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        pass_hash = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
            ("admin", pass_hash, "Administrador Sistema", "Admin"),
        )
        op_hash = hashlib.sha256("1234".encode()).hexdigest()
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
            ("operador", op_hash, "Operador Depósito", "Operador"),
        )

    conn.commit()
    conn.close()


def obtener_conexion():
    return sqlite3.connect(DB_NAME)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verificar_credenciales(username, password):
    conn = obtener_conexion()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, nombre, rol FROM usuarios WHERE username = ? AND password_hash = ?",
        (username, hash_password(password)),
    )
    user = cursor.fetchone()
    conn.close()
    return user


# --- INICIALIZACIÓN ---
init_db()
st.set_page_config(
    page_title="Control de Stock - Neumáticos", page_icon="🛞", layout="wide"
)

# --- CONTROL DE SESIÓN / LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.nombre_usuario = None
    st.session_state.rol = None

if not st.session_state.autenticado:
    st.title("🛞 Sistema de Control de Stock de Neumáticos")
    st.subheader("Acceso al Sistema")

    with st.form("form_login"):
        username_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")
        btn_login = st.form_submit_button("Iniciar Sesión")

        if btn_login:
            user_info = verificar_credenciales(username_input, password_input)
            if user_info:
                st.session_state.autenticado = True
                st.session_state.usuario = user_info[0]
                st.session_state.nombre_usuario = user_info[1]
                st.session_state.rol = user_info[2]
                st.success(f"Bienvenido/a {user_info[1]}")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.markdown(f"👤 **Usuario:** {st.session_state.nombre_usuario}")
st.sidebar.markdown(f"🔑 **Rol:** {st.session_state.rol}")

if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.nombre_usuario = None
    st.session_state.rol = None
    st.rerun()

st.sidebar.divider()

if st.session_state.rol == "Visualizador":
    opciones_menu = ["📦 Visualizar Stock & Alertas"]
elif st.session_state.rol == "Operador":
    opciones_menu = [
        "📦 Visualizar Stock & Alertas",
        "✏️ Ajustar DOT",
        "🔄 Transferir Ubicación",
        "📥 Registrar Ingreso",
        "📂 Carga Masiva (Excel/CSV)",
        "📤 Registrar Egreso",
        "📋 Historial y Exportación",
    ]
else:  # Admin
    opciones_menu = [
        "📦 Visualizar Stock & Alertas",
        "✏️ Ajustar DOT",
        "🔄 Transferir Ubicación",
        "📥 Registrar Ingreso",
        "📂 Carga Masiva (Excel/CSV)",
        "📤 Registrar Egreso",
        "📋 Historial y Exportación",
        "⚙️ Gestión de Usuarios",
    ]

opcion = st.sidebar.radio("Menú Principal", opciones_menu)

st.title("🛞 Control de Stock de Neumáticos")

# --- VISTA 1: VISUALIZAR STOCK & ALERTAS ---
if opcion == "📦 Visualizar Stock & Alertas":
    st.header("Stock Actual de Neumáticos")

    conn = obtener_conexion()
    df_stock = pd.read_sql_query(
        "SELECT id, medida, dot, ubicacion, cantidad FROM inventario WHERE cantidad > 0",
        conn,
    )
    conn.close()

    if df_stock.empty:
        st.info("No hay neumáticos en stock actualmente.")
    else:
        anio_actual = datetime.now().year
        df_stock["anio_dot"] = df_stock["dot"].apply(
            lambda x: 2000 + int(str(x)[2:])
            if (len(str(x)) == 4 and str(x).isdigit())
            else anio_actual
        )
        df_stock["antiguedad_anios"] = anio_actual - df_stock["anio_dot"]

        df_stock = df_stock.sort_values(
            by=["antiguedad_anios", "medida"], ascending=[False, True]
        )

        st.subheader("⚠️ Alerta de Rotación y Edición de DOT")
        st.caption(
            "Podés hacer doble clic sobre las celdas de la columna **DOT** para corregir el código. Las cantidades y ubicaciones están protegidas."
        )

        df_mostrar = df_stock[
            ["id", "medida", "dot", "ubicacion", "cantidad", "antiguedad_anios"]
        ].copy()
        df_mostrar.columns = [
            "ID",
            "Medida",
            "DOT",
            "Ubicación",
            "Cantidad",
            "Antigüedad (Años)",
        ]

        df_editado = st.data_editor(
            df_mostrar,
            disabled=[
                "ID",
                "Medida",
                "Ubicación",
                "Cantidad",
                "Antigüedad (Años)",
            ],
            use_container_width=True,
            num_rows="fixed",
            key="editor_stock",
        )

        if st.button("💾 Guardar Cambios de DOT en Pantalla"):
            conn = obtener_conexion()
            cursor = conn.cursor()
            cambios_realizados = 0

            for index, row in df_editado.iterrows():
                id_item = int(row["ID"])
                nuevo_dot = str(row["DOT"]).strip().zfill(4)

                if len(nuevo_dot) == 4 and nuevo_dot.isdigit():
                    nuevo_anio_dot = 2000 + int(nuevo_dot[2:])
                    cursor.execute(
                        """
                        UPDATE inventario 
                        SET dot=?, anio_dot=? 
                        WHERE id=?
                    """,
                        (nuevo_dot, nuevo_anio_dot, id_item),
                    )
                    cambios_realizados += 1

            conn.commit()
            conn.close()
            st.success(
                f"✅ Se actualizaron los códigos DOT correctamente ({cambios_realizados} registros)."
            )
            st.rerun()

# --- VISTA 2: AJUSTAR DOT DE UN ARTÍCULO ---
elif opcion == "✏️ Ajustar DOT":
    st.header("✏️ Ajustar / Reasignar DOT de un Lote")
    st.write(
        "Permite corregir el DOT de una parte (o la totalidad) de las unidades de un lote."
    )

    conn = obtener_conexion()
    df_disponible = pd.read_sql_query(
        "SELECT id, medida, dot, ubicacion, cantidad FROM inventario WHERE cantidad > 0",
        conn,
    )
    conn.close()

    if df_disponible.empty:
        st.warning("No hay neumáticos registrados en el inventario.")
    else:
        df_disponible["item_label"] = df_disponible.apply(
            lambda x: f"ID: {x['id']} | Medida: {x['medida']} | DOT Actual: {x['dot']} | Ubicación: {x['ubicacion']} | Disponibles: {x['cantidad']}",
            axis=1,
        )

        item_seleccionado = st.selectbox(
            "Seleccione el lote a reasignar:",
            options=df_disponible["item_label"].tolist(),
        )

        id_sel = int(item_seleccionado.split("|")[0].replace("ID:", "").strip())
        row_sel = df_disponible[df_disponible["id"] == id_sel].iloc[0]

        cant_max = int(row_sel["cantidad"])

        with st.form("form_ajuste_dot", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                st.text_input(
                    "Medida", value=row_sel["medida"], disabled=True
                )
                st.text_input(
                    "DOT Actual", value=str(row_sel["dot"]), disabled=True
                )
                cant_a_reasignar = st.number_input(
                    f"Cantidad a reasignar (Máx: {cant_max})",
                    min_value=1,
                    max_value=cant_max,
                    value=1,
                    step=1,
                )

            with col2:
                nuevo_dot = st.text_input(
                    "Nuevo DOT (4 dígitos, ej: 1523)", max_chars=4
                )
                nueva_ubicacion = st.text_input(
                    "Ubicación Destino", value=str(row_sel["ubicacion"])
                ).upper()
                ref_doc = st.text_input(
                    "Motivo / Documento de Ajuste",
                    placeholder="Corrección visual de DOT / Revisión física",
                )

            btn_guardar_ajuste = st.form_submit_button("Aplicar Reasignación")

            if btn_guardar_ajuste:
                if (
                    not nuevo_dot
                    or len(nuevo_dot) != 4
                    or not nuevo_dot.isdigit()
                    or not ref_doc
                ):
                    st.error(
                        "Por favor complete el nuevo DOT (4 números) y el motivo del ajuste."
                    )
                elif (
                    nuevo_dot == str(row_sel["dot"])
                    and nueva_ubicacion == str(row_sel["ubicacion"])
                ):
                    st.warning(
                        "El nuevo DOT y la ubicación son idénticos a los actuales. No hay cambios que realizar."
                    )
                else:
                    nuevo_anio_dot = 2000 + int(nuevo_dot[2:])
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    usuario_actual = st.session_state.usuario
                    medida_sel = row_sel["medida"]

                    conn = obtener_conexion()
                    cursor = conn.cursor()

                    cant_restante = cant_max - cant_a_reasignar
                    if cant_restante > 0:
                        cursor.execute(
                            "UPDATE inventario SET cantidad=? WHERE id=?",
                            (cant_restante, id_sel),
                        )
                    else:
                        cursor.execute(
                            "DELETE FROM inventario WHERE id=?", (id_sel,)
                        )

                    cursor.execute(
                        "SELECT id, cantidad FROM inventario WHERE medida=? AND dot=? AND ubicacion=?",
                        (medida_sel, nuevo_dot, nueva_ubicacion),
                    )
                    lote_existente = cursor.fetchone()

                    if lote_existente:
                        nueva_cant_existente = (
                            lote_existente[1] + cant_a_reasignar
                        )
                        cursor.execute(
                            "UPDATE inventario SET cantidad=? WHERE id=?",
                            (nueva_cant_existente, lote_existente[0]),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO inventario (medida, dot, anio_dot, ubicacion, cantidad) VALUES (?, ?, ?, ?, ?)",
                            (
                                medida_sel,
                                nuevo_dot,
                                nuevo_anio_dot,
                                nueva_ubicacion,
                                cant_a_reasignar,
                            ),
                        )

                    cursor.execute(
                        """
                        INSERT INTO movimientos (fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario)
                        VALUES (?, 'REASIGNACIÓN DOT', ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            fecha_actual,
                            medida_sel,
                            nuevo_dot,
                            nueva_ubicacion,
                            cant_a_reasignar,
                            f"Reasignado desde DOT {row_sel['dot']} -> {nuevo_dot}",
                            ref_doc,
                            usuario_actual,
                        ),
                    )

                    conn.commit()
                    conn.close()
                    st.success(
                        f"✅ Se reasignaron {cant_a_reasignar} unidad(es) al DOT {nuevo_dot}. Quedan {cant_restante} en el DOT anterior."
                    )
                    st.rerun()

# --- VISTA 3: TRANSFERIR ENTRE UBICACIONES ---
elif opcion == "🔄 Transferir Ubicación":
    st.header("🔄 Transferencia de Neumáticos Entre Ubicaciones")
    st.write(
        "Mover stock de una ubicación a otra manteniendo el mismo código DOT."
    )

    conn = obtener_conexion()
    df_disponible = pd.read_sql_query(
        "SELECT id, medida, dot, ubicacion, cantidad FROM inventario WHERE cantidad > 0",
        conn,
    )
    conn.close()

    if df_disponible.empty:
        st.warning("No hay neumáticos disponibles para mover.")
    else:
        df_disponible["item_label"] = df_disponible.apply(
            lambda x: f"ID: {x['id']} | Medida: {x['medida']} | DOT: {x['dot']} | Origen: {x['ubicacion']} | Disponibles: {x['cantidad']}",
            axis=1,
        )

        item_seleccionado = st.selectbox(
            "Seleccione el lote a transferir:",
            options=df_disponible["item_label"].tolist(),
        )

        id_sel = int(item_seleccionado.split("|")[0].replace("ID:", "").strip())
        row_sel = df_disponible[df_disponible["id"] == id_sel].iloc[0]

        cant_max = int(row_sel["cantidad"])

        with st.form("form_transferencia", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                st.text_input(
                    "Medida", value=row_sel["medida"], disabled=True
                )
                st.text_input("DOT", value=str(row_sel["dot"]), disabled=True)
                st.text_input(
                    "Ubicación Origen",
                    value=row_sel["ubicacion"],
                    disabled=True,
                )

            with col2:
                cant_transferir = st.number_input(
                    f"Cantidad a mover (Máx: {cant_max})",
                    min_value=1,
                    max_value=cant_max,
                    value=1,
                    step=1,
                )
                ubicacion_destino = st.text_input(
                    "Ubicación Destino (ej: RACK-B2)", placeholder="RACK-B2"
                ).upper()
                ref_doc = st.text_input(
                    "Referencia Documental / Orden de Movimiento",
                    placeholder="Remito Interno #401",
                )

            btn_transferir = st.form_submit_button("Confirmar Transferencia")

            if btn_transferir:
                if not ubicacion_destino or not ref_doc:
                    st.error(
                        "Debe ingresar la ubicación destino y la referencia documental."
                    )
                elif ubicacion_destino == str(row_sel["ubicacion"]):
                    st.warning(
                        "La ubicación de destino debe ser diferente a la de origen."
                    )
                else:
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    usuario_actual = st.session_state.usuario
                    medida_sel = row_sel["medida"]
                    dot_sel = str(row_sel["dot"])
                    anio_dot_sel = 2000 + int(dot_sel[2:])
                    ubic_origen = str(row_sel["ubicacion"])

                    conn = obtener_conexion()
                    cursor = conn.cursor()

                    # 1. Descontar del origen
                    cant_restante = cant_max - cant_transferir
                    if cant_restante > 0:
                        cursor.execute(
                            "UPDATE inventario SET cantidad=? WHERE id=?",
                            (cant_restante, id_sel),
                        )
                    else:
                        cursor.execute(
                            "DELETE FROM inventario WHERE id=?", (id_sel,)
                        )

                    # 2. Agregar o sumar al destino
                    cursor.execute(
                        "SELECT id, cantidad FROM inventario WHERE medida=? AND dot=? AND ubicacion=?",
                        (medida_sel, dot_sel, ubicacion_destino),
                    )
                    destino_existente = cursor.fetchone()

                    if destino_existente:
                        nueva_cant = destino_existente[1] + cant_transferir
                        cursor.execute(
                            "UPDATE inventario SET cantidad=? WHERE id=?",
                            (nueva_cant, destino_existente[0]),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO inventario (medida, dot, anio_dot, ubicacion, cantidad) VALUES (?, ?, ?, ?, ?)",
                            (
                                medida_sel,
                                dot_sel,
                                anio_dot_sel,
                                ubicacion_destino,
                                cant_transferir,
                            ),
                        )

                    # 3. Registrar en Auditoría
                    cursor.execute(
                        """
                        INSERT INTO movimientos (fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario)
                        VALUES (?, 'TRANSFERENCIA', ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            fecha_actual,
                            medida_sel,
                            dot_sel,
                            f"{ubic_origen} -> {ubicacion_destino}",
                            cant_transferir,
                            f"Mapeo de Stock: {ubic_origen} a {ubicacion_destino}",
                            ref_doc,
                            usuario_actual,
                        ),
                    )

                    conn.commit()
                    conn.close()
                    st.success(
                        f"✅ Se movieron {cant_transferir} unidades a '{ubicacion_destino}' exitosamente."
                    )
                    st.rerun()

# --- VISTA 4: REGISTRAR INGRESO INDIVIDUAL ---
elif opcion == "📥 Registrar Ingreso":
    st.header("Registrar Ingreso Individual")

    with st.form("form_ingreso", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            medida = st.text_input(
                "Medida (ej: 205/55 R16)", placeholder="205/55 R16"
            ).upper()
            dot = st.text_input(
                "DOT (4 dígitos, ej: 1222)", max_chars=4, placeholder="1222"
            )
            cantidad = st.number_input("Cantidad", min_value=1, step=1)

        with col2:
            ubicacion = st.text_input(
                "Ubicación / Estante", placeholder="RACK-A1"
            ).upper()
            ref_documental = st.text_input(
                "Referencia Documental",
                placeholder="Factura A-0001 / Remito 1234",
            )
            motivo = st.selectbox(
                "Motivo de Ingreso",
                [
                    "Compra Bridgestone",
                    "Compra importado",
                    "Ajuste de stock/Alta",
                    "Recepción CD",
                    "Otro",
                ],
            )

        submitted = st.form_submit_button("Guardar Ingreso")

        if submitted:
            if (
                not medida
                or not dot
                or len(dot) != 4
                or not dot.isdigit()
                or not ubicacion
                or not ref_documental
            ):
                st.error(
                    "Por favor, complete todos los campos correctamente. El DOT debe tener 4 números."
                )
            else:
                anio_dot = 2000 + int(dot[2:])
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                usuario_actual = st.session_state.usuario

                conn = obtener_conexion()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT id, cantidad FROM inventario WHERE medida=? AND dot=? AND ubicacion=?",
                    (medida, dot, ubicacion),
                )
                item = cursor.fetchone()

                if item:
                    nueva_cant = item[1] + cantidad
                    cursor.execute(
                        "UPDATE inventario SET cantidad=? WHERE id=?",
                        (nueva_cant, item[0]),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO inventario (medida, dot, anio_dot, ubicacion, cantidad) VALUES (?, ?, ?, ?, ?)",
                        (medida, dot, anio_dot, ubicacion, cantidad),
                    )

                cursor.execute(
                    """
                    INSERT INTO movimientos (fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario)
                    VALUES (?, 'INGRESO', ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fecha_actual,
                        medida,
                        dot,
                        ubicacion,
                        cantidad,
                        motivo,
                        ref_documental,
                        usuario_actual,
                    ),
                )

                conn.commit()
                conn.close()
                st.success(
                    f"✅ Se registraron {cantidad} unidad(es) correctamente por el usuario '{usuario_actual}'."
                )

# --- VISTA 5: CARGA MASIVA DE STOCK (EXCEL / CSV) ---
elif opcion == "📂 Carga Masiva (Excel/CSV)":
    st.header("📂 Carga Masiva de Neumáticos")
    st.write(
        "Subí un archivo Excel (`.xlsx`) o un archivo `.csv` para cargar múltiples cubiertas en simultáneo."
    )

    ejemplo_csv = "medida,dot,ubicacion,cantidad,ref_documental\n205/55 R16,1222,RACK-A1,10,Carga Inicial 2026\n175/65 R14,0819,ESTANTE-B2,4,Carga Inicial 2026"

    st.download_button(
        label="📥 Descargar Plantilla de Ejemplo (.csv / abrible con Excel)",
        data=ejemplo_csv,
        file_name="plantilla_carga_masiva.csv",
        mime="text/csv",
    )

    st.divider()

    archivo_subido = st.file_uploader(
        "Seleccioná el archivo Excel (.xlsx) o CSV (.csv) para importar:",
        type=["xlsx", "csv"],
    )

    if archivo_subido is not None:
        try:
            if archivo_subido.name.endswith(".csv"):
                df_cargado = pd.read_csv(archivo_subido, dtype={"dot": str})
            else:
                df_cargado = pd.read_excel(archivo_subido, dtype={"dot": str})

            df_cargado.columns = [
                str(c).strip().lower() for c in df_cargado.columns
            ]

            columnas_requeridas = [
                "medida",
                "dot",
                "ubicacion",
                "cantidad",
                "ref_documental",
            ]
            columnas_faltantes = [
                col
                for col in columnas_requeridas
                if col not in df_cargado.columns
            ]

            if columnas_faltantes:
                st.error(
                    f"El archivo no contiene las columnas requeridas: {', '.join(columnas_faltantes)}"
                )
            else:
                st.subheader("Vista previa de los datos a importar:")
                st.dataframe(df_cargado, use_container_width=True)

                if st.button("🚀 Confirmar e Importar Carga Masiva"):
                    conn = obtener_conexion()
                    cursor = conn.cursor()
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    usuario_actual = st.session_state.usuario

                    registros_procesados = 0

                    for _, row in df_cargado.iterrows():
                        medida_i = str(row["medida"]).strip().upper()
                        dot_i = str(row["dot"]).strip().zfill(4)
                        ubicacion_i = str(row["ubicacion"]).strip().upper()
                        cant_i = int(row["cantidad"])
                        ref_doc_i = str(row["ref_documental"]).strip()
                        anio_dot_i = 2000 + int(dot_i[2:])

                        cursor.execute(
                            "SELECT id, cantidad FROM inventario WHERE medida=? AND dot=? AND ubicacion=?",
                            (medida_i, dot_i, ubicacion_i),
                        )
                        item = cursor.fetchone()

                        if item:
                            nueva_cant = item[1] + cant_i
                            cursor.execute(
                                "UPDATE inventario SET cantidad=? WHERE id=?",
                                (nueva_cant, item[0]),
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO inventario (medida, dot, anio_dot, ubicacion, cantidad) VALUES (?, ?, ?, ?, ?)",
                                (medida_i, dot_i, anio_dot_i, ubicacion_i, cant_i),
                            )

                        cursor.execute(
                            """
                            INSERT INTO movimientos (fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario)
                            VALUES (?, 'INGRESO', ?, ?, ?, ?, 'Carga Masiva / Inicial', ?, ?)
                        """,
                            (
                                fecha_actual,
                                medida_i,
                                dot_i,
                                ubicacion_i,
                                cant_i,
                                ref_doc_i,
                                usuario_actual,
                            ),
                        )
                        registros_procesados += 1

                    conn.commit()
                    conn.close()
                    st.success(
                        f"🎉 ¡Éxito! Se importaron {registros_procesados} líneas correctamente."
                    )
                    st.rerun()

        except Exception as e:
            st.error(f"Error al procesar el archivo. Detalle: {e}")

# --- VISTA 6: REGISTRAR EGRESO ---
elif opcion == "📤 Registrar Egreso":
    st.header("Registrar Egreso de Neumáticos")

    conn = obtener_conexion()
    df_disponible = pd.read_sql_query(
        "SELECT id, medida, dot, ubicacion, cantidad FROM inventario WHERE cantidad > 0",
        conn,
    )
    conn.close()

    if df_disponible.empty:
        st.warning("No hay neumáticos disponibles en el inventario para egresar.")
    else:
        df_disponible["item_label"] = df_disponible.apply(
            lambda x: f"ID: {x['id']} | Medida: {x['medida']} | DOT: {x['dot']} | Ubicación: {x['ubicacion']} | Disponibles: {x['cantidad']}",
            axis=1,
        )

        item_seleccionado = st.selectbox(
            "Seleccione el neumático a egresar:",
            options=df_disponible["item_label"].tolist(),
        )

        id_sel = int(item_seleccionado.split("|")[0].replace("ID:", "").strip())
        row_sel = df_disponible[df_disponible["id"] == id_sel].iloc[0]

        with st.form("form_egreso", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                cantidad_egreso = st.number_input(
                    "Cantidad a retirar",
                    min_value=1,
                    max_value=int(row_sel["cantidad"]),
                    step=1,
                )
                motivo_egreso = st.selectbox(
                    "Motivo de Egreso",
                    [
                        "VENTA",
                        "GARANTÍA / DEFECTO",
                        "AJUSTE DE STOCK / PÉRDIDA",
                        "USO INTERNO / MUESTRA",
                    ],
                )

            with col2:
                ref_documental = st.text_input(
                    "Referencia Documental",
                    placeholder="Factura B-0052 / Reclamo Gar. #991",
                )

            submitted_egreso = st.form_submit_button("Confirmar Egreso")

            if submitted_egreso:
                if not ref_documental:
                    st.error(
                        "Debe ingresar la Referencia Documental para poder registrar la salida."
                    )
                else:
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    usuario_actual = st.session_state.usuario

                    conn = obtener_conexion()
                    cursor = conn.cursor()

                    nueva_cantidad = row_sel["cantidad"] - cantidad_egreso
                    cursor.execute(
                        "UPDATE inventario SET cantidad=? WHERE id=?",
                        (nueva_cantidad, id_sel),
                    )

                    cursor.execute(
                        """
                        INSERT INTO movimientos (fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario)
                        VALUES (?, 'EGRESO', ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            fecha_actual,
                            row_sel["medida"],
                            row_sel["dot"],
                            row_sel["ubicacion"],
                            cantidad_egreso,
                            motivo_egreso,
                            ref_documental,
                            usuario_actual,
                        ),
                    )

                    conn.commit()
                    conn.close()
                    st.success("✅ Egreso registrado exitosamente.")
                    st.rerun()

# --- VISTA 7: HISTORIAL Y EXPORTACIÓN ---
elif opcion == "📋 Historial y Exportación":
    st.header("Historial de Movimientos y Exportación")

    conn = obtener_conexion()
    df_mov = pd.read_sql_query(
        "SELECT id, fecha, tipo_movimiento, medida, dot, ubicacion, cantidad, motivo, ref_documental, usuario FROM movimientos ORDER BY id DESC",
        conn,
    )
    df_stock_exp = pd.read_sql_query(
        "SELECT id, medida, dot, anio_dot, ubicacion, cantidad FROM inventario WHERE cantidad > 0",
        conn,
    )
    conn.close()

    st.subheader("📊 Exportación de Datos")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        if not df_stock_exp.empty:
            anio_actual = datetime.now().year
            df_stock_exp["antiguedad_anios"] = (
                anio_actual - df_stock_exp["anio_dot"]
            )
            df_stock_exp.columns = [
                "ID",
                "Medida",
                "DOT",
                "Año DOT",
                "Ubicación",
                "Cantidad",
                "Antigüedad (Años)",
            ]
            csv_stock = df_stock_exp.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Descargar Stock Actual (.csv / Excel)",
                data=csv_stock,
                file_name=f"stock_actual_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

    with col_exp2:
        if not df_mov.empty:
            df_mov_exp = df_mov.copy()
            df_mov_exp.columns = [
                "ID",
                "Fecha/Hora",
                "Tipo Movimiento",
                "Medida",
                "DOT",
                "Ubicación / Movimiento",
                "Cantidad",
                "Motivo",
                "Ref. Documental",
                "Usuario",
            ]
            csv_mov = df_mov_exp.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Descargar Historial Movimientos (.csv / Excel)",
                data=csv_mov,
                file_name=f"historial_movimientos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

    st.divider()
    st.subheader("Tabla de Auditoría de Movimientos")
    if df_mov.empty:
        st.info("Aún no hay movimientos registrados.")
    else:
        df_mov.columns = [
            "ID",
            "Fecha/Hora",
            "Tipo",
            "Medida",
            "DOT",
            "Ubicación / Movimiento",
            "Cantidad",
            "Motivo",
            "Ref. Documental",
            "Usuario",
        ]
        st.dataframe(df_mov, use_container_width=True)

# --- VISTA 8: GESTIÓN DE USUARIOS ---
elif opcion == "⚙️ Gestión de Usuarios":
    st.header("⚙️ Gestión de Usuarios del Sistema")

    st.subheader("Crear Nuevo Usuario")
    with st.form("form_nuevo_usuario", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nuevo_user = st.text_input("Nombre de Usuario (Login)")
            nuevo_nombre = st.text_input("Nombre Completo")
        with col2:
            nueva_pass = st.text_input("Contraseña", type="password")
            nuevo_rol = st.selectbox(
                "Rol", ["Visualizador", "Operador", "Admin"]
            )

        btn_crear_user = st.form_submit_button("Guardar Usuario")
        if btn_crear_user:
            if not nuevo_user or not nuevo_nombre or not nueva_pass:
                st.error("Todos los campos son obligatorios.")
            else:
                conn = obtener_conexion()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT username FROM usuarios WHERE username = ?",
                    (nuevo_user,),
                )
                if cursor.fetchone():
                    st.error("El nombre de usuario ya existe.")
                else:
                    cursor.execute(
                        "INSERT INTO usuarios (username, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
                        (
                            nuevo_user,
                            hash_password(nueva_pass),
                            nuevo_nombre,
                            nuevo_rol,
                        ),
                    )
                    conn.commit()
                    st.success(
                        f"✅ Usuario '{nuevo_user}' creado exitosamente con el rol '{nuevo_rol}'."
                    )
                conn.close()

    st.divider()
    st.subheader("Usuarios Registrados")
    conn = obtener_conexion()
    df_users = pd.read_sql_query(
        "SELECT username, nombre, rol FROM usuarios", conn
    )
    conn.close()
    st.dataframe(df_users, use_container_width=True)
