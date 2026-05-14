# Printer Factory Sim — instrucciones para Claude Code

## Regla permanente: Manufacturer Manager

Cuando la conversación trate del **manufacturer** (pedidos a retailer, inventario, stock terminado, compras al proveedor, precios mayoristas, capacidad, producción, o interpretar un día simulado como responsable de fábrica):

1. **Lee y aplica** el fichero **`skills/manufacturer-manager.md`** completo al planear o ejecutar pasos.
2. Usa **solo** los comandos que ese documento lista (vía `./start_cli.sh` desde `manufacturer/`).
3. Respeta las prohibiciones explícitas de la skill (p. ej. el turn engine controla el tiempo; no avances el día simulado con el CLI del fabricante).

Si esos requisitos chocan con otros documentos del repo **para el mismo modo “fabricante”**, prevalece **`skills/manufacturer-manager.md`**.

## Resto del contexto del proyecto

La guía larga de arquitectura y convenciones está en **`claude.md`** (nombre en minúsculas). Úsala para cambios de código, estructura del repo y desarrollo general; no sustituye la skill cuando el encargo es operar como manufacturer.
