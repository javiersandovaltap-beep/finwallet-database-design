#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlkeWallet — Interfaz CLI Python
Conexión a MySQL para gestión de monedero virtual.
Requiere: pip install mysql-connector-python
"""

import sys
from dotenv import load_dotenv
import os
import mysql.connector
from mysql.connector import Error
from getpass import getpass

load_dotenv()
# ================================================================
# CONFIGURACIÓN DE CONEXIÓN
# ================================================================

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'AlkeWallet'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '')
}


# ================================================================
# CONEXIÓN
# ================================================================

def crear_conexion(password):
    """Crea y retorna la conexión a la base de datos MySQL.

    Args:
        password (str): Contraseña del usuario MySQL.

    Returns:
        connection | None: Objeto de conexión o None si falla.
    """
    try:
        config = {**DB_CONFIG, 'password': password}
        conexion = mysql.connector.connect(**config)
        if conexion.is_connected():
            return conexion
    except Error as e:
        print(f"\n  ✖ Error de conexión: {e}")
        return None


# ================================================================
# MENÚ
# ================================================================

def mostrar_menu():
    """Muestra el menú principal en consola."""
    print("\n" + "=" * 45)
    print("        💳  ALKEWALLET — MENÚ PRINCIPAL")
    print("=" * 45)
    print("  1. Ver todos los usuarios")
    print("  2. Ver todas las transacciones")
    print("  3. Ver transacciones de un usuario")
    print("  4. Realizar transferencia")
    print("  5. Agregar nuevo usuario")
    print("  6. Ver reporte de actividad")
    print("  0. Salir")
    print("-" * 45)


def pedir_opcion():
    """Solicita y valida una opción del menú.

    Returns:
        int: Opción válida entre 0 y 6, o -1 si es inválida.
    """
    try:
        opcion = int(input("  Seleccione una opción (0-6): ").strip())
        if opcion < 0 or opcion > 6:
            print("  Error: Ingrese un número entre 0 y 6.")
            return -1
        return opcion
    except ValueError:
        return -1


# ================================================================
# OPERACIONES
# ================================================================

def ver_usuarios(conexion):
    """Muestra todos los usuarios registrados con su saldo y moneda.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            u.user_id,
            u.nombre,
            u.correo_electronico,
            u.saldo,
            m.currency_symbol AS moneda
        FROM usuario u
        INNER JOIN moneda m ON u.currency_id = m.currency_id
        ORDER BY u.user_id
    """)
    usuarios = cursor.fetchall()
    cursor.close()

    if not usuarios:
        print("\n  Sin usuarios registrados.")
        return

    print(f"\n  {'ID':<5} {'NOMBRE':<20} {'CORREO':<25} {'SALDO':>12} {'MON':<5}")
    print("  " + "-" * 70)
    for u in usuarios:
        print(f"  {u['user_id']:<5} {u['nombre']:<20} {u['correo_electronico']:<25} "
              f"${u['saldo']:>10,.2f} {u['moneda']:<5}")
    print(f"\n  Total de usuarios: {len(usuarios)}")


def ver_transacciones(conexion):
    """Muestra todas las transacciones con nombres de emisor y receptor.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            t.transaction_id   AS id,
            s.nombre           AS emisor,
            r.nombre           AS receptor,
            t.importe,
            t.transaction_date AS fecha
        FROM transaccion t
        INNER JOIN usuario s ON t.sender_user_id   = s.user_id
        INNER JOIN usuario r ON t.receiver_user_id = r.user_id
        ORDER BY t.transaction_date DESC
    """)
    transacciones = cursor.fetchall()
    cursor.close()

    if not transacciones:
        print("\n  Sin transacciones registradas.")
        return

    print(f"\n  {'ID':<5} {'EMISOR':<18} {'RECEPTOR':<18} {'IMPORTE':>12}  {'FECHA':<20}")
    print("  " + "-" * 78)
    for t in transacciones:
        fecha = t['fecha'].strftime('%Y-%m-%d %H:%M') if t['fecha'] else '—'
        print(f"  {t['id']:<5} {t['emisor']:<18} {t['receptor']:<18} "
              f"${t['importe']:>10,.2f}  {fecha:<20}")
    print(f"\n  Total de transacciones: {len(transacciones)}")


def ver_transacciones_usuario(conexion):
    """Muestra todas las transacciones de un usuario específico.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    try:
        user_id = int(input("\n  Ingrese el ID del usuario: ").strip())
    except ValueError:
        print("  Error: ID debe ser un número entero.")
        return

    cursor = conexion.cursor(dictionary=True)

    # Verificar que el usuario existe
    cursor.execute("SELECT nombre FROM usuario WHERE user_id = %s", (user_id,))
    usuario = cursor.fetchone()
    if not usuario:
        print(f"  Error: No existe un usuario con ID {user_id}.")
        cursor.close()
        return

    cursor.execute("""
        SELECT
            t.transaction_id AS id,
            s.nombre         AS emisor,
            r.nombre         AS receptor,
            t.importe,
            t.transaction_date AS fecha
        FROM transaccion t
        INNER JOIN usuario s ON t.sender_user_id   = s.user_id
        INNER JOIN usuario r ON t.receiver_user_id = r.user_id
        WHERE t.sender_user_id = %s OR t.receiver_user_id = %s
        ORDER BY t.transaction_date DESC
    """, (user_id, user_id))
    transacciones = cursor.fetchall()
    cursor.close()

    print(f"\n  Transacciones de: {usuario['nombre']}")
    if not transacciones:
        print("  Este usuario no tiene transacciones.")
        return

    print(f"\n  {'ID':<5} {'EMISOR':<18} {'RECEPTOR':<18} {'IMPORTE':>12}  {'FECHA':<20}")
    print("  " + "-" * 78)
    for t in transacciones:
        fecha = t['fecha'].strftime('%Y-%m-%d %H:%M') if t['fecha'] else '—'
        print(f"  {t['id']:<5} {t['emisor']:<18} {t['receptor']:<18} "
              f"${t['importe']:>10,.2f}  {fecha:<20}")


def realizar_transferencia(conexion):
    """Ejecuta una transferencia entre dos usuarios usando START TRANSACTION / COMMIT.
    Revierte con ROLLBACK si ocurre cualquier error.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    print("\n  --- REALIZAR TRANSFERENCIA ---")

    try:
        sender_id   = int(input("  ID del emisor  : ").strip())
        receiver_id = int(input("  ID del receptor: ").strip())
        importe     = float(input("  Importe        : $").strip())
    except ValueError:
        print("  Error: Valores inválidos.")
        return

    cursor = conexion.cursor(dictionary=True)

    # Validar emisor
    cursor.execute("SELECT nombre, saldo FROM usuario WHERE user_id = %s", (sender_id,))
    emisor = cursor.fetchone()
    if not emisor:
        print(f"  Error: Emisor con ID {sender_id} no existe.")
        cursor.close()
        return

    # Validar receptor
    cursor.execute("SELECT nombre FROM usuario WHERE user_id = %s", (receiver_id,))
    receptor = cursor.fetchone()
    if not receptor:
        print(f"  Error: Receptor con ID {receiver_id} no existe.")
        cursor.close()
        return

    # Validar auto-transferencia
    if sender_id == receiver_id:
        print("  Error: No puede transferirse dinero a sí mismo.")
        cursor.close()
        return

    # Validar saldo
    if importe <= 0:
        print("  Error: El importe debe ser mayor a $0.")
        cursor.close()
        return

    if emisor['saldo'] < importe:
        print(f"  Error: Saldo insuficiente. Disponible: ${emisor['saldo']:,.2f}")
        cursor.close()
        return

    # Confirmar operación
    print(f"\n  Emisor  : {emisor['nombre']} (saldo actual: ${emisor['saldo']:,.2f})")
    print(f"  Receptor: {receptor['nombre']}")
    print(f"  Importe : ${importe:,.2f}")
    confirmacion = input("\n  ¿Confirmar transferencia? (s/n): ").strip().lower()

    if confirmacion != 's':
        print("  Operación cancelada.")
        cursor.close()
        return

    # Ejecutar transacción ACID
    try:
        conexion.start_transaction()

        cursor.execute(
            "UPDATE usuario SET saldo = saldo - %s WHERE user_id = %s",
            (importe, sender_id)
        )
        cursor.execute(
            "UPDATE usuario SET saldo = saldo + %s WHERE user_id = %s",
            (importe, receiver_id)
        )
        cursor.execute(
            "INSERT INTO transaccion (sender_user_id, receiver_user_id, importe) VALUES (%s, %s, %s)",
            (sender_id, receiver_id, importe)
        )

        conexion.commit()
        print(f"\n  ✔ Transferencia exitosa. ID transacción: {cursor.lastrowid}")

    except Error as e:
        conexion.rollback()
        print(f"\n  ✖ Error — Transacción revertida (ROLLBACK): {e}")
    finally:
        cursor.close()


def agregar_usuario(conexion):
    """Registra un nuevo usuario en el sistema.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    print("\n  --- AGREGAR USUARIO ---")

    # Mostrar monedas disponibles
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT currency_id, currency_name, currency_symbol FROM moneda")
    monedas = cursor.fetchall()
    print("\n  Monedas disponibles:")
    for m in monedas:
        print(f"    {m['currency_id']}. {m['currency_name']} ({m['currency_symbol']})")

    nombre    = input("\n  Nombre           : ").strip()
    correo    = input("  Correo           : ").strip()
    password  = input("  Contraseña       : ").strip()

    try:
        saldo      = float(input("  Saldo inicial    : $").strip())
        currency   = int(input("  ID de moneda     : ").strip())
    except ValueError:
        print("  Error: Saldo o moneda inválidos.")
        cursor.close()
        return

    try:
        cursor.execute("""
            INSERT INTO usuario (nombre, correo_electronico, contrasena, saldo, currency_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombre, correo, password, saldo, currency))
        conexion.commit()
        print(f"\n  ✔ Usuario '{nombre}' registrado con ID: {cursor.lastrowid}")
    except Error as e:
        print(f"\n  ✖ Error al registrar usuario: {e}")
    finally:
        cursor.close()


def ver_reporte(conexion):
    """Muestra un reporte de actividad general usando la vista v_resumen_usuarios.

    Args:
        conexion: Objeto de conexión MySQL activo.
    """
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM v_resumen_usuarios ORDER BY monto_total_enviado DESC")
    reporte = cursor.fetchall()
    cursor.close()

    if not reporte:
        print("\n  Sin datos para el reporte.")
        return

    saldo_total = sum(r['saldo'] for r in reporte)

    print(f"\n  {'USUARIO':<20} {'MON':<5} {'SALDO':>12} {'ENVIADAS':>9} {'RECIBIDAS':>10} {'TOTAL ENV':>12}")
    print("  " + "-" * 75)
    for r in reporte:
        print(f"  {r['nombre']:<20} {r['moneda']:<5} ${r['saldo']:>10,.2f} "
              f"{r['total_enviadas']:>9} {r['total_recibidas']:>10} "
              f"${r['monto_total_enviado']:>10,.2f}")
    print("  " + "-" * 75)
    print(f"  {'SALDO TOTAL EN SISTEMA':<20} {'':5} ${saldo_total:>10,.2f}")


# ================================================================
# MAIN
# ================================================================

def main():
    """Punto de entrada. Solicita credenciales y ejecuta el bucle principal."""
    print("\n" + "=" * 45)
    print("   💳  ALKEWALLET — SISTEMA DE TRANSFERENCIAS")
    print("=" * 45)

    conexion = crear_conexion(DB_CONFIG['password'])

    if not conexion:
        print("  No se pudo conectar. Verifica que MySQL esté activo y las credenciales sean correctas.")
        sys.exit(1)

    print("  ✔ Conexión establecida con AlkeWallet\n")

    opciones = {
        1: lambda: ver_usuarios(conexion),
        2: lambda: ver_transacciones(conexion),
        3: lambda: ver_transacciones_usuario(conexion),
        4: lambda: realizar_transferencia(conexion),
        5: lambda: agregar_usuario(conexion),
        6: lambda: ver_reporte(conexion),
    }

    while True:
        mostrar_menu()
        opcion = pedir_opcion()

        if opcion == -1:
            continue
        if opcion == 0:
            conexion.close()
            print("\n  Conexión cerrada. ¡Hasta pronto!\n")
            sys.exit(0)

        opciones[opcion]()


if __name__ == "__main__":
    main()
