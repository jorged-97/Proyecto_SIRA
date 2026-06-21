from utils.db import get_connection
from models.auditoria_model import AuditoriaModel
from typing import Optional, Dict, Tuple, List
from datetime import date


class ColaboracionModel:

    @staticmethod
    def registrar(
        estudiante_id: int,
        anio_escolar_id: int,
        colaboro: bool,
        usuario_actual: dict
    ) -> Tuple[bool, str]:
        if not isinstance(estudiante_id, int) or estudiante_id <= 0:
            return False, "ID de estudiante inválido"
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return False, "ID de año escolar inválido"
        if not usuario_actual or 'id' not in usuario_actual:
            return False, "Usuario inválido"

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return False, "Error de conexión a la base de datos"

            cursor = conexion.cursor(dictionary=True)
            conexion.start_transaction()

            cursor.execute(
                "SELECT id, colaboro FROM colaboracion_inscripcion WHERE estudiante_id = %s AND anio_escolar_id = %s",
                (estudiante_id, anio_escolar_id)
            )
            existente = cursor.fetchone()

            valor_nuevo = 1 if colaboro else 0

            if existente:
                if existente['colaboro'] == valor_nuevo:
                    conexion.rollback()
                    return True, "Sin cambios en la colaboración"

                cursor.execute(
                    "UPDATE colaboracion_inscripcion SET colaboro = %s, fecha_registro = %s, registrado_por = %s WHERE id = %s",
                    (valor_nuevo, date.today(), usuario_actual["id"], existente['id'])
                )
                registro_id = existente['id']
            else:
                cursor.execute(
                    """INSERT INTO colaboracion_inscripcion (estudiante_id, anio_escolar_id, colaboro, fecha_registro, registrado_por)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (estudiante_id, anio_escolar_id, valor_nuevo, date.today(), usuario_actual["id"])
                )
                registro_id = cursor.lastrowid

            conexion.commit()

            texto = "Sí" if colaboro else "No"
            AuditoriaModel.registrar(
                usuario_id=usuario_actual["id"],
                accion="STATUS_CHANGE",
                entidad="colaboracion_inscripcion",
                entidad_id=registro_id,
                referencia=f"estudiante_id={estudiante_id}",
                descripcion=f"Colaboración de inscripción marcada como {texto} para estudiante {estudiante_id}"
            )

            return True, f"Colaboración registrada como {texto}"

        except Exception as e:
            if conexion:
                conexion.rollback()
            return False, f"Error al registrar colaboración: {str(e)}"
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def obtener(estudiante_id: int, anio_escolar_id: int) -> Optional[bool]:
        if not isinstance(estudiante_id, int) or estudiante_id <= 0:
            return None
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return None

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return None

            cursor = conexion.cursor()
            cursor.execute(
                "SELECT colaboro FROM colaboracion_inscripcion WHERE estudiante_id = %s AND anio_escolar_id = %s",
                (estudiante_id, anio_escolar_id)
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else None

        except Exception as e:
            print(f"Error obteniendo colaboración: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def obtener_estado_actual(estudiante_id: int) -> Optional[bool]:
        if not isinstance(estudiante_id, int) or estudiante_id <= 0:
            return None

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return None

            cursor = conexion.cursor(dictionary=True)

            cursor.execute("SELECT id FROM anio_escolar WHERE es_actual = 1 LIMIT 1")
            anio = cursor.fetchone()
            if not anio:
                return None

            cursor.execute(
                """SELECT COALESCE(ci.colaboro, 0) AS colaboro
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = se.estudiante_id AND ci.anio_escolar_id = %s
                   WHERE se.estudiante_id = %s AND s.año_escolar_id = %s AND s.activo = 1
                   LIMIT 1""",
                (anio['id'], estudiante_id, anio['id'])
            )
            row = cursor.fetchone()
            return bool(row['colaboro']) if row else False

        except Exception as e:
            print(f"Error obteniendo estado actual de colaboración: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def asegurar_registro(estudiante_id: int, anio_escolar_id: int) -> Tuple[bool, str]:
        if not isinstance(estudiante_id, int) or estudiante_id <= 0:
            return False, "ID de estudiante inválido"
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return False, "ID de año escolar inválido"

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return False, "Error de conexión"

            cursor = conexion.cursor()
            cursor.execute(
                "SELECT id FROM colaboracion_inscripcion WHERE estudiante_id = %s AND anio_escolar_id = %s",
                (estudiante_id, anio_escolar_id)
            )
            if cursor.fetchone():
                return True, "Registro ya existe"

            cursor.execute(
                """INSERT IGNORE INTO colaboracion_inscripcion (estudiante_id, anio_escolar_id, colaboro)
                   VALUES (%s, %s, 0)""",
                (estudiante_id, anio_escolar_id)
            )
            conexion.commit()
            return True, "Registro creado"

        except Exception as e:
            return False, f"Error: {str(e)}"
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def inicializar_anio(anio_escolar_id: int, usuario_actual: dict = None) -> Tuple[bool, str]:
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return False, "ID de año escolar inválido"

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return False, "Error de conexión"

            cursor = conexion.cursor(dictionary=True)

            cursor.execute(
                """SELECT DISTINCT se.estudiante_id
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   WHERE s.año_escolar_id = %s AND e.estado = 1""",
                (anio_escolar_id,)
            )
            estudiantes = cursor.fetchall()

            insertados = 0
            for est in estudiantes:
                cursor.execute(
                    """INSERT IGNORE INTO colaboracion_inscripcion (estudiante_id, anio_escolar_id, colaboro)
                       VALUES (%s, %s, 0)""",
                    (est['estudiante_id'], anio_escolar_id)
                )
                if cursor.rowcount > 0:
                    insertados += 1

            conexion.commit()

            if usuario_actual:
                AuditoriaModel.registrar(
                    usuario_id=usuario_actual.get("id", 0),
                    accion="APERTURA_AÑO",
                    entidad="colaboracion_inscripcion",
                    entidad_id=anio_escolar_id,
                    referencia=str(anio_escolar_id),
                    descripcion=f"Inicialización de colaboración para nuevo año escolar: {insertados} registros creados"
                )

            return True, f"Colaboración inicializada: {insertados} registros"

        except Exception as e:
            if conexion:
                conexion.rollback()
            return False, f"Error al inicializar colaboración: {str(e)}"
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def listar_por_anio(anio_escolar_id: int) -> List[Dict]:
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return []

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return []

            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                """SELECT e.id AS estudiante_id, e.cedula, e.nombres, e.apellidos,
                          COALESCE(s.grado, 'Sin asignar') AS grado,
                          COALESCE(s.letra, 'Sin asignar') AS letra,
                          COALESCE(s.nivel, 'Sin asignar') AS nivel,
                          COALESCE(ci.colaboro, 0) AS colaboro,
                          ci.fecha_registro,
                          r.nombres AS repre_nombres, r.apellidos AS repre_apellidos
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = e.id AND ci.anio_escolar_id = %s
                   LEFT JOIN representantes r ON e.representante_id = r.id
                   WHERE s.año_escolar_id = %s AND s.activo = 1 AND e.estado = 1
                   ORDER BY e.apellidos, e.nombres""",
                (anio_escolar_id, anio_escolar_id)
            )
            return cursor.fetchall()

        except Exception as e:
            print(f"Error listando colaboración por año: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def contar_colaboracion_anio(anio_escolar_id: int) -> Dict:
        resultado = {"total": 0, "colaboraron": 0, "no_colaboraron": 0, "porcentaje": 0.0}
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return resultado

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return resultado

            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                """SELECT COUNT(DISTINCT e.id) AS total,
                          SUM(CASE WHEN COALESCE(ci.colaboro, 0) = 1 THEN 1 ELSE 0 END) AS colaboraron,
                          SUM(CASE WHEN COALESCE(ci.colaboro, 0) = 0 THEN 1 ELSE 0 END) AS no_colaboraron
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = e.id AND ci.anio_escolar_id = %s
                   WHERE s.año_escolar_id = %s AND s.activo = 1 AND e.estado = 1""",
                (anio_escolar_id, anio_escolar_id)
            )
            row = cursor.fetchone()
            if row:
                resultado["total"] = row["total"] or 0
                resultado["colaboraron"] = row["colaboraron"] or 0
                resultado["no_colaboraron"] = row["no_colaboraron"] or 0
                if resultado["total"] > 0:
                    resultado["porcentaje"] = round(
                        (resultado["colaboraron"] / resultado["total"]) * 100, 1
                    )

            return resultado

        except Exception as e:
            print(f"Error contando colaboración: {e}")
            return resultado
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def obtener_estadisticas_por_seccion(anio_escolar_id: int) -> List[Dict]:
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return []

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return []

            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                """SELECT CONCAT(s.grado, ' ', s.letra) AS seccion,
                          COUNT(DISTINCT e.id) AS total,
                          SUM(CASE WHEN COALESCE(ci.colaboro, 0) = 1 THEN 1 ELSE 0 END) AS colaboraron,
                          SUM(CASE WHEN COALESCE(ci.colaboro, 0) = 0 THEN 1 ELSE 0 END) AS no_colaboraron
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = e.id AND ci.anio_escolar_id = %s
                   WHERE s.año_escolar_id = %s AND s.activo = 1 AND e.estado = 1
                   GROUP BY s.id, s.grado, s.letra
                   ORDER BY s.grado, s.letra""",
                (anio_escolar_id, anio_escolar_id)
            )
            return cursor.fetchall()

        except Exception as e:
            print(f"Error obteniendo estadísticas por sección: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def obtener_mapa_colaboracion_anio(anio_escolar_id: int) -> Dict[int, bool]:
        if not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return {}

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return {}

            cursor = conexion.cursor()
            cursor.execute(
                """SELECT e.id, COALESCE(ci.colaboro, 0)
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = e.id AND ci.anio_escolar_id = %s
                   WHERE s.año_escolar_id = %s AND s.activo = 1 AND e.estado = 1""",
                (anio_escolar_id, anio_escolar_id)
            )
            return {row[0]: bool(row[1]) for row in cursor.fetchall()}

        except Exception as e:
            print(f"Error obteniendo mapa de colaboración: {e}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()

    @staticmethod
    def listar_colaboracion_por_seccion(grado: str, letra: str, anio_escolar_id: int) -> List[Dict]:
        if not grado or not letra or not isinstance(anio_escolar_id, int) or anio_escolar_id <= 0:
            return []

        conexion = None
        cursor = None
        try:
            conexion = get_connection()
            if not conexion:
                return []

            cursor = conexion.cursor(dictionary=True)
            cursor.execute(
                """SELECT e.id, e.cedula, e.nombres, e.apellidos,
                          TIMESTAMPDIFF(YEAR, e.fecha_nac, CURDATE()) AS edad,
                          e.genero,
                          COALESCE(ci.colaboro, 0) AS colaboro
                   FROM seccion_estudiante se
                   JOIN secciones s ON se.seccion_id = s.id
                   JOIN estudiantes e ON se.estudiante_id = e.id
                   LEFT JOIN colaboracion_inscripcion ci ON ci.estudiante_id = e.id AND ci.anio_escolar_id = %s
                   WHERE s.grado = %s AND s.letra = %s
                   AND s.año_escolar_id = %s AND s.activo = 1 AND e.estado = 1
                   ORDER BY e.apellidos, e.nombres""",
                (anio_escolar_id, grado, letra, anio_escolar_id)
            )
            return cursor.fetchall()

        except Exception as e:
            print(f"Error listando colaboración por sección: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conexion and conexion.is_connected():
                conexion.close()
