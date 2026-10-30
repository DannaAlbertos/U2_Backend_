# Actividad 5

## Fundamentos de arquitectura    
### Actividad 5 – Configuración de servicios 


### Estudiantes: 
- Albertos Sosa Danna Pamela  
- Cetzal Cetzal Astrit Airan 
- Díaz Anduze Giovana Ruby 
- Alemán Venus Getsemaní 
  
### Docente: Gimer Almicar Cervera Evia 
  
- 4°A



#### Mérida, Yucatán a 17 de octubre de 2026  


### E03

![E03](img\E03.1.png)
![E03](img\E03.png)
![E03](img\E03.2.png)
![E03](img\E03.3.png)

### Caso E06. Entradas inválidas (Previsualización)

| Variante | Entrada (`input`) | Mensaje devuelto | Estado en Base de Datos |
| :--- | :--- | :--- | :--- |
| **Propuesta sobre ADMINISTRADOR** | `roleId: 1`, `permissionIds: ["1", "2"]` | `"No se pueden modificar los permisos del rol ADMINISTRADOR"` | Sin cambios (Validación Fail-Fast previa a ejecución) |
| **Permisos repetidos** | `roleId: 5`, `permissionIds: ["1", "1"]` | `"La lista de permisos contiene IDs duplicados"` | Sin cambios (Rechazo inmediato sin alterar BD) |
| **Permiso inexistente** | `roleId: 3`, `permissionIds: ["9999"]` | `"Uno o más permisos deseados no existen o están inactivos"` | Sin cambios (Rechazo previo a BD) |
| **Rol inexistente** | `roleId: "9999"`, `permissionIds: ["1", "2"]` | `"El rol no existe o está inactivo"` | Sin cambios (Rechazo previo a BD) |


 ````Evidencias en la carpeta img````