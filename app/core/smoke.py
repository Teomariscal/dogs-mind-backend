"""
Cuentas de smoke test — aisladas del censo real de usuarios.

El smoke test (tools/smoke-tests/smoke_test.py, LaunchAgent cada 6 h) registra
cuentas de verdad contra producción para comprobar que el alta por delegación y
el alta de embajador siguen vivas. Son altas reales: tienen que pasar por
/auth/register o no comprueban nada.

El efecto secundario es que se quedaban en la tabla. A 4 altas por pasada y 4
pasadas al día, en junio-octubre de 2026 se acumularon 1.646 filas sobre 2.088:
el 79 % del panel de "Gestión de usuarios" era basura nuestra, y no había forma
de ver si había entrado un usuario nuevo (founder, 10-oct-2026).

Dos medidas, aquí las dos:

  1. `purgar_antiguas()` — cada alta de smoke borra las de pasadas anteriores,
     así que en la tabla nunca hay más que la pasada en curso. Autolimpiante:
     sin cron, sin credenciales, sin nada que mantener.
  2. `es_smoke()` — el panel de admin las filtra, por si alguna sobrevive (una
     pasada a medias, un cambio de dominio) o por si alguien mira la tabla en la
     hora siguiente a la pasada.

El dominio NO tiene MX ni se usa para nada más: cualquier cosa en
@dogsmindsmoke.net es nuestra por definición.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

SMOKE_DOMAIN = "dogsmindsmoke.net"
SMOKE_EMAIL_LIKE = f"%@{SMOKE_DOMAIN}"

# Cuentas borradas: el borrado de cuenta es un scrub (GDPR) que conserva la fila
# con email deleted-<id>@thedogsmind.deleted para no romper los registros de
# pago. Tampoco son usuarios, así que el panel tampoco las cuenta.
DELETED_EMAIL_LIKE = "%@thedogsmind.deleted"

# Margen antes de borrar una cuenta de smoke. Una pasada entera tarda segundos;
# una hora deja sitio de sobra para mirar la tabla después de una pasada si algo
# ha fallado, sin que se acumule nada.
RETENCION_HORAS = 1


def es_smoke(email: str) -> bool:
    """¿Es una cuenta creada por el smoke test?"""
    return (email or "").strip().lower().endswith("@" + SMOKE_DOMAIN)


def purgar_antiguas(db: Session, horas: int = RETENCION_HORAS) -> int:
    """
    Borra las cuentas de smoke de más de `horas`. Devuelve cuántas borró.

    Borrado duro, no scrub: estas cuentas no tienen pagos ni nada que conservar
    (comprobado 10-oct-2026 sobre las 1.646 que había: 0 dogs, 0 cases, 0
    payments, 0 usage_log, 0 safety_log — el smoke test solo llama a
    /auth/register). Si alguna vez llegaran a tener hijos, el DELETE falla por
    la FK y lo veríamos en los logs en vez de dejar huérfanos.

    Nunca lanza: si el borrado falla, el alta que lo disparó tiene que seguir
    adelante igual — el smoke test está para comprobar el alta, no la limpieza.
    """
    from app.models.user import User

    corte = datetime.utcnow() - timedelta(hours=horas)
    try:
        n = (
            db.query(User)
            .filter(User.email.like(SMOKE_EMAIL_LIKE), User.created_at < corte)
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(n or 0)
    except Exception as e:
        db.rollback()
        print(f"[smoke] purga fallida: {e}")
        return 0
