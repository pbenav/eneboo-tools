# encoding: UTF-8
u"""
    Módulo de cálculo y aplicación de parches emulando flpatch.
"""
"""
    -----
    Hay que anotar de algún modo cuando parcheamos una clase, qué clase 
    estábamos buscando. Esto servirá para que la próxima clase que busque esa
    misma, en su lugar herede de la nuestra y así preservar el correcto orden
    de aplicación.
    
    Ejemplo:
    
    class jasper extends num_serie /** %from: oficial */ {
    
    
    Aunque pueda parecer información excesiva, es normal, porque genera un 
    arbol 1->N y da la información exacta de la extensión/mezcla al usuario
    final.
    
"""

import re, os.path

def qsclass_reader(iface, file_name, file_lines):
    linelist = []
    classes = []
    declidx = {}
    defidx = {}
    iface = None
    for n,line in enumerate(file_lines):
        m = re.search("/\*\*\s*@(\w+)\s+(\w+)?\s*\*/", line)
        if m:
            dtype = m.group(1)
            cname = m.group(2)
            npos = len(linelist)
            if dtype == "class_declaration":
                if cname in classes:
                    iface.error(u"Redefinición de la clase %s (file: %s)" % (cname,file_name))
                else:
                    classes.append(cname)
                    declidx[cname] = npos
            elif dtype == "class_definition":
                defidx[cname] = npos
            elif dtype == "file":
                # el tipo @file no lo gestionamos
                pass 
            else:
                iface.warn(u"Tipo de identificador doxygen no reconocido %s (file: %s)" % (repr(dtype),file_name))
                continue
                
            found = [ dtype , cname, n ]
            if len(linelist): 
                linelist[-1].append(n) 
            linelist.append(found)
        # const iface = new ifaceCtx( this );
        m = re.search("(const|var)\s+iface\s*=\s*new\s*(?P<classname>\w+)\(\s*this\s*\);?", line) 
        if m:
            iface = {
                'block' : len(linelist) - 1,
                'classname' : m.group('classname'),
                'line' : n,
                'text' : m.group(0),
            }

    linelist[-1].append(len(file_lines)) 
    classlist = {
        "decl" : declidx,
        "def" : defidx,
        "classes" : classes,
        "list" : linelist,
        "iface" : iface
        }
    return classlist
    
        
def extract_class_decl_info(iface,text_lines):
    classdict = {}
    for n,line in enumerate(text_lines):
        m = re.search("class\s+(?P<cname>\w+)(\s+extends\s+(?P<cbase>\w+))?(\s+/\*\*\s+%from:\s+(?P<cfrom>\w+)\s+\*/)?",line)
        if m:
            cname = m.group("cname")
            classdict[cname] = {
                'name' : cname,
                'extends' : m.group("cbase"),
                'from' : m.group("cfrom"),
                'text': m.group(0),
                'line' : n,
                }
    return classdict

    

def file_reader(filename):
    try:
        f1 = open(filename, "r")
    except IOError,e: 
        iface.error("File Not Found: %s" % repr(filename))
        return
    name = os.path.basename(filename)
    return name, [line.rstrip() for line in f1.readlines()]
    

def diff_qs(iface, base, final):
    iface.debug(u"Procesando Diff QS $base:%s -> $final:%s" % (base, final))
    nbase, flbase = file_reader(base)
    nfinal, flfinal = file_reader(final)
    if flbase is None or flfinal is None:
        iface.info(u"Abortando Diff QS por error al abrir los ficheros")
        return
    clbase = qsclass_reader(iface, base, flbase)
    clfinal = qsclass_reader(iface, final, flfinal)
    created_classes_s = list(set(clfinal['classes']) - set(clbase['classes']))
    deleted_classes = list(set(clbase['classes']) - set(clfinal['classes']))
    # Mantener el orden en que se encontraron:
    created_classes = [ clname for clname in clfinal['classes'] if clname in created_classes_s ]
    
    if len(created_classes) == 0:
        iface.warn(u"No se han detectado clases nuevas. El parche quedará vacío. ($final:%s)" % (final))
        
    if len(deleted_classes) > 0:
        iface.warn(u"Se han borrado clases. Este cambio no se registrará en el parche. ($final:%s)" % (final))
        
    iface.debug2r(created = created_classes, deleted = deleted_classes)
    iface.output.write("\n")
    iface_line = -1
    if clfinal['iface']:
        iface_line = clfinal['iface']['line']
    
    for clname in created_classes:
        block_decl = clfinal['decl'].get(clname,None)
        if block_decl is None:
            iface.error(u"Se esperaba una declaración de clase para %s." % clname)
            continue
        dtype, clname, idx1, idx2 = clfinal['list'][block_decl]
        iface.debug2r(exported_block=clfinal['list'][block_decl])
        
        lines = flfinal[idx1:idx2]
        if iface_line >= idx1 and iface_line < idx2:
            # Excluir la definición "iface" del parche, en caso de que estuviese dentro
            rel_line = iface_line - idx1
            from_text = clfinal['iface']['text']
            assert( lines[rel_line].find(from_text) != -1 )
            lines[rel_line] = lines[rel_line].replace(from_text,"")
        text = "\n".join(lines) 
        iface.output.write(text)
        
    iface.output.write("\n")
    
    for clname in created_classes:
        block_def = clfinal['def'].get(clname,None)
        if block_def is None:
            iface.warn(u"Se esperaba una definición de clase para %s." % clname)
            continue
        dtype, clname, idx1, idx2 = clfinal['list'][block_def]
        iface.debug2r(exported_block=clfinal['list'][block_def])
        lines = flfinal[idx1:idx2]
        text = "\n".join(lines) 
        iface.output.write(text)
        

def check_qs_classes(iface, base):
    iface.debug(u"Comprobando clases del fichero QS $filename:%s" % (base))
    nbase, flbase = file_reader(base)
    if flbase is None:
        iface.info(u"Abortando comprobación por error al abrir los ficheros")
        return
    clbase = qsclass_reader(iface, base, flbase)
    classdict = extract_class_decl_info(iface, flbase)
    
    if not clbase['iface']:
        iface.error(u"No encontramos declaración de iface.")
        return
    iface_clname = clbase['iface']['classname']
    iface.debug(u"Se encontró declaración iface de la clase %s" % (repr(iface_clname)))
    # Buscar clases duplicadas primero. 
    # Los tests no se ejecutaran bien si tienen clases duplicadas.
    for clname in set(clbase['classes']):
        count = clbase['classes'].count(clname)
        if count > 1:
            iface.error("La clase %s se encontró %d veces" % (clname,count))            
            return
    
    if iface_clname not in classdict:
        iface.error("La declaración de iface requiere una clase %s"
                    " que no existe." % (iface_clname))
        return
    not_used_classes = clbase['classes'][:]
    iface_class_hierarchy = []
    current_class = iface_clname
    prev_class = "<no-class>"
    if clbase['iface']['line'] < classdict[current_class]['line']:
        iface.warn("La declaración de iface requiere una clase %s"
                    " que está definida más abajo en el código" % (current_class))
    while True:
        if current_class not in not_used_classes:
            if current_class in clbase['classes']:
                iface.error("La clase %s es parte de una "
                            "referencia circular (desde: %s)" % 
                            (current_class, prev_class))
            else:
                iface.error("La clase %s no está "
                            "definida (desde: %s)" % 
                            (current_class, prev_class))
            return
        not_used_classes.remove(current_class)
        iface_class_hierarchy.insert(0, current_class)
        parent = classdict[current_class]['extends']        
        if parent is None: break
        if classdict[current_class]['line'] < classdict[parent]['line']:
            iface.error("La clase %s hereda de una clase %s que está"
                        " definida más abajo en el código" % (current_class, parent))
            return
        current_class = parent

    # De las clases sobrantes, ninguna puede heredar de alguna que hayamos usado
    for clname in not_used_classes:
        parent = classdict[clname]['extends']        
        if parent in iface_class_hierarchy:
            iface.error("La clase %s no la heredó iface, y sin embargo,"
                        " hereda de la clase %s que sí la heredó." % (clname, parent))
            return
    iface.debug2r(classes=iface_class_hierarchy)
    iface.info2(u"La comprobación se completó sin errores.")
    return True
    
    
    
    
def patch_qs(iface, base, patch):
    iface.debug(u"Procesando Patch QS $base:%s + $patch:%s" % (base, patch))
    nbase, flbase = file_reader(base)
    npatch, flpatch = file_reader(patch)
    if flbase is None or flpatch is None:
        iface.info(u"Abortando Patch QS por error al abrir los ficheros")
        return
    # classlist
    clpatch = qsclass_reader(iface, patch, flpatch) 
    # classdict
    cdpatch = extract_class_decl_info(iface, flpatch) 
    
    if clpatch['iface']:
        iface.error(u"El parche contiene una definición de iface. No se puede aplicar.")
        return
    
    iface.debug2r(clpatch=clpatch)
    iface.debug2r(cdpatch=cdpatch)
    
    # Hallar el trabajo a realizar:
    #  - Hay que insertar en "base" las clases especificadas por clpatch['classes']
    #       en el mismo orden en el que aparecen.
    #  - Al insertar la clase agregamos en el extends un /** %from: clname */
    #       que indicará qué clase estábamos buscando.
    #  - Cuando insertemos una nueva clase, hay que ajustar las llamadas a la
    #       clase padre de la clase insertada y de la nueva clase hija
    #  - En caso de no haber nueva clase hija, entonces "iface" cambia de tipo.
    #       Además, probablemente haya que bajar la definición de iface.
    
    for newclass in clpatch['classes']:
        clbase = qsclass_reader(iface, base, flbase) 
        cdbase = extract_class_decl_info(iface, flbase) 
        # TODO: const iface = .... puede no existir en base.
        iface.debug(u"Procediendo a la inserción de la clase %s" % newclass)
        if newclass in clbase['classes']:
            iface.warn(u"La clase %s ya estaba insertada en el fichero, "
                        u"omitimos el parcheo de esta clase." % newclass)
            continue
        # debería heredar de su extends, o su from (si existe). 
        # si carece de extends es un error y se omite.
        extends = cdpatch[newclass]['extends']
        if extends is None:
            iface.error(u"La clase %s carece de extends y no es insertable como"
                        u" un parche." % newclass)
            continue
        cfrom = cdpatch[newclass]['from']
        if cfrom: 
            iface.info2(u"class %s: Se ha especificado un %from %s y "
                        u"tomará precedencia por encima del extends %s" % (
                        newclass, cfrom, extends) )
            extends = cfrom
        if extends not in clbase['classes']:
            iface.error(u"La clase %s debía heredar de %s, pero no "
                        u"la encontramos en el fichero base." % (newclass,extends))
            continue
        iface.debug(u"La clase %s deberá heredar de %s" % (newclass,extends))
        
        # Buscar la clase más inferior que heredó originalmente de "extends"
        extending = extends
        for classname in reversed(clbase['classes']):
            # Buscamos del revés para encontrar el último.
            cdict = cdbase[classname]
            if cdict['from'] == extends:
                extending = cdict['name']
                iface.debug(u"La clase %s es la última que heredó de %s, pasamos a heredar de ésta." % (extending,extends))
                break
        
        # Habrá que insertar el bloque entre dos bloques: parent_class y child_class.
        # Vamos a asumir que estos bloques están juntos y que child_class heredaba de parent_class.
        parent_class = clbase['decl'][extending]
        # Dónde guardar el código de definición: (después de la clase que extendimos)
        try:
            child_def_block = clbase['def'][extending] + 1 
        except KeyError:
            iface.warn(u"No hemos encontrado el bloque de código para las "
                       u"definiciones de la clase %s, pondremos las nuevas al"
                       u" final del fichero." % (extending))
            child_def_block = max(clbase['def'].values()) + 1 
           
        assert(clbase['list'][parent_class][1] == extending) # <- este calculo deberia ser correcto. 
        
        child_class = -1 # Supuestamente es el siguiente bloque de tipo "class_declaration".
        for n, litem in enumerate(clbase['list'][parent_class:]):
            if n == 0: continue
            if litem[0] != "class_declaration": continue
            child_class = parent_class + n
            break
        
        if child_class >= 0:
            prev_child_cname = clbase['list'][child_class][1]
            # $prev_child_name debería estar heredando de $extending.
            if cdbase[prev_child_cname]['extends'] != extending:
                iface.error(u"Se esperaba que la clase %s heredara de "
                            u"%s, pero en cambio hereda de %s" % (prev_child_cname,extending,cdbase[prev_child_cname]['extends']))
                continue                    
            else:
                iface.debug(u"La clase %s hereda de %s, pasará a heredar %s" % (prev_child_cname,extending,newclass))
                # TODO: Configurar herencia de $prev_child_name
        else:
            # Si no había clase posterior, entonces marcamos como posición
            # de inserción el próximo bloque.
            child_class = parent_class + 1
            
        # Si la clase que vamos a heredar es la que está en el iface, entonces 
        #   en el iface habrá que cambiarlo por la nuestra.
        if clbase['iface']: # -> primero comprobar que tenemos iface.
            iface.debug2r(iface=clbase['iface'])
            if clbase['iface']['classname'] == extending:
                iface.debug(u"La clase que estamos extendiendo (%s) es el "
                        u"tipo de dato usado por iface, por lo tanto actualizamos"
                        u" el tipo de dato usado por iface a %s" % (extending, classname))
                # TODO: Actualizar iface.
        else:
            iface.warn("No existe declaración de iface en el código (aplicando patch para clase %s)" % newclass)
                
        # Si la clase del parche que estamos aplicando pasa a extender otra 
        # clase con nombre distinto, actualizaremos también los constructores.
        if cdpatch[newclass]['extends'] != extending:
            iface.debug(u"La clase %s extendía %s en el parche, pasará a"
                    u" heredar a la clase %s" % (classname, 
                        cdpatch[newclass]['extends'], extending))
            # TODO: Actualizar constructores del parche.
            
        # Bloques a insertar:
        newblocklist = clbase['list'][:]
        
        from_def_block = clpatch['list'][clpatch['def'][newclass]]
        # incrustamos en posicion $child_def_block
        newblocklist.insert(child_def_block, from_def_block)
        
        # Se hace en orden inverso (primero abajo, luego arriba) para evitar
        # descuadres, por tanto asumimos:
        assert(child_def_block > child_class)
        
        
        from_decl_block = clpatch['list'][clpatch['decl'][newclass]]
        # incrustamos en posicion $child_class
        newblocklist.insert(child_class, from_decl_block)
        
        newbase = [] # empezamos la creación del nuevo fichero
        
        # insertamos las líneas de cabecera (hasta el primer bloque)
        idx1 = clbase['list'][0][2]
        newbase += flbase[:idx1]
        
        # iteramos por la lista de bloques y vamos procesando.
        for btype, bname, idx1, idx2 in newblocklist:
            # ATENCION: Sabemos que un bloque viene del parche o de base porque
            # .. tiene la clase $newclass que no está en base. Si esta condición
            # .. no se cumple, entonces el algoritmo falla.
            if bname == newclass: source = "patch"
            else: source = "base"
            
            if source == "base":
                newbase += flbase[idx1:idx2]
            elif source == "patch":
                newbase += flpatch[idx1:idx2]
            else: raise AssertionError
        
        iface.debug2r(newblocklist=newblocklist)
        # Ya tenemos el fichero montado:
        
        
        #  -> clpatch[list][
            
        
        
