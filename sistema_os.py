import sqlite3
import flet as ft
from datetime import datetime
import uuid

# Adicione esta função ao seu código para verificar e atualizar o banco existente
def migrar_banco_se_necessario():
    conn = sqlite3.connect('sistema_os.db')
    cursor = conn.cursor()
    
    # Verifica se a coluna data_cadastro existe na tabela clientes
    try:
        cursor.execute("SELECT data_cadastro FROM clientes LIMIT 1")
    except sqlite3.OperationalError:
        # A coluna não existe, vamos adicioná-la
        print("Migrando banco de dados: adicionando coluna data_cadastro à tabela clientes")
        cursor.execute("ALTER TABLE clientes ADD COLUMN data_cadastro TEXT")
        # Define um valor padrão para registros existentes
        data_padrao = datetime.now().strftime('%d/%m/%Y %H:%M')
        cursor.execute("UPDATE clientes SET data_cadastro = ?", (data_padrao,))
    
    conn.commit()
    conn.close()

migrar_banco_se_necessario()  # Adicione esta linha antes de usar o banco

# Adicione uma função de migração para converter os IDs existentes
def migrar_para_novos_ids():
    """Migra os IDs de UUID para IDs sequenciais."""
    conn = sqlite3.connect('sistema_os.db')
    cursor = conn.cursor()
    
    try:
        # Verifica se precisamos migrar
        cursor.execute("PRAGMA table_info(clientes)")
        columns = [col[1] for col in cursor.fetchall()]
        if "id_antigo" in columns:
            print("Migração já realizada anteriormente.")
            return
        
        # Backup das tabelas antes da migração
        print("Iniciando migração de IDs. Fazendo backup das tabelas...")
        tables = ["clientes", "equipamentos", "produtos", "tecnicos", "ordens_servico"]
        for table in tables:
            cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        
        # Recria as tabelas com a mesma estrutura
        init_db()
        
        # Mapeamento de IDs antigos para novos
        id_mapping = {
            "clientes": {},
            "equipamentos": {},
            "produtos": {},
            "tecnicos": {},
            "ordens_servico": {}
        }
        
        # Migra clientes
        print("Migrando clientes...")
        cursor.execute("SELECT * FROM clientes_old")
        clientes = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(clientes_old)")
        cliente_columns = [col[1] for col in cursor.fetchall()]
        
        for i, cliente in enumerate(clientes):
            data = {cliente_columns[j]: cliente[j] for j in range(len(cliente_columns))}
            old_id = data['id']
            new_id = f"CLI{i+1:05d}"
            id_mapping["clientes"][old_id] = new_id
            
            # Adiciona coluna id_antigo
            cursor.execute("ALTER TABLE clientes ADD COLUMN id_antigo TEXT")
            
            # Insere com o novo ID
            cursor.execute(f'''
                INSERT INTO clientes (id, nome, telefone, email, rua, numero, bairro, cidade, estado, data_cadastro, id_antigo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                new_id, 
                data.get('nome'), 
                data.get('telefone'), 
                data.get('email'),
                data.get('rua'),
                data.get('numero'),
                data.get('bairro'),
                data.get('cidade'),
                data.get('estado'),
                data.get('data_cadastro'),
                old_id
            ))
        
        # Migração similar para outras tabelas...
        # Código para equipamentos, produtos, técnicos e ordens de serviço
        
        print("Migração concluída com sucesso!")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a migração: {e}")
        # Restaura as tabelas originais se houver erro
        for table in ["clientes", "equipamentos", "produtos", "tecnicos", "ordens_servico"]:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                cursor.execute(f"ALTER TABLE {table}_old RENAME TO {table}")
            except:
                pass
    finally:
        conn.close()

# Inicialização do Banco de Dados
def init_db():
    conn = sqlite3.connect('sistema_os.db')
    cursor = conn.cursor()
    
    # Verificamos que a tabela de clientes tem a coluna data_cadastro
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            email TEXT,
            rua TEXT,
            numero TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            data_cadastro TEXT
        )
    ''')
    
    # Tabela Equipamentos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipamentos (
            id TEXT PRIMARY KEY,
            cliente_id TEXT,
            tipo TEXT NOT NULL,
            marca TEXT,
            modelo TEXT,
            numero_serie TEXT,
            observacao TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')
    
    # Tabela Produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL,
            quantidade INTEGER
        )
    ''')
    
    # Tabela Ordens de Serviço
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id TEXT PRIMARY KEY,
            cliente_id TEXT,
            equipamento_id TEXT,
            tecnico_id TEXT,
            data_abertura TEXT,
            data_fechamento TEXT,
            status TEXT,
            descricao_problema TEXT,
            descricao_solucao TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (equipamento_id) REFERENCES equipamentos(id),
            FOREIGN KEY (tecnico_id) REFERENCES tecnicos(id)
        )
    ''')
    
    # Tabela Técnicos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tecnicos (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            especialidade TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Funções de CRUD
class SistemaOS:
    def __init__(self):
        self.conn = sqlite3.connect('sistema_os.db')
        # Inicializa contadores para cada tipo de entidade
        self._init_counters()
    
    def _init_counters(self):
        """Inicializa contadores para IDs sequenciais baseados no maior ID existente"""
        cursor = self.conn.cursor()
        # Para clientes (formato: CLI00001)
        cursor.execute("SELECT id FROM clientes ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_id = result[0] if result else "CLI00000"
        self.cliente_counter = int(last_id[3:]) if last_id.startswith("CLI") else 0
        
        # Para equipamentos (formato: EQP00001)
        cursor.execute("SELECT id FROM equipamentos ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_id = result[0] if result else "EQP00000"
        self.equip_counter = int(last_id[3:]) if last_id.startswith("EQP") else 0
        
        # Para produtos (formato: PRD00001)
        cursor.execute("SELECT id FROM produtos ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_id = result[0] if result else "PRD00000"
        self.produto_counter = int(last_id[3:]) if last_id.startswith("PRD") else 0
        
        # Para técnicos (formato: TEC00001)
        cursor.execute("SELECT id FROM tecnicos ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_id = result[0] if result else "TEC00000"
        self.tecnico_counter = int(last_id[3:]) if last_id.startswith("TEC") else 0
        
        # Para ordens de serviço (formato: OS00001)
        cursor.execute("SELECT id FROM ordens_servico ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        last_id = result[0] if result else "OS00000"
        self.os_counter = int(last_id[2:]) if last_id.startswith("OS") else 0
    
    # Métodos para gerar novos IDs
    def _get_next_id(self, prefix, counter_attr):
        counter = getattr(self, counter_attr) + 1
        setattr(self, counter_attr, counter)
        return f"{prefix}{counter:05d}"  # formato: PREFIX + 5 dígitos com zeros à esquerda
    
    def get_next_cliente_id(self):
        return self._get_next_id("CLI", "cliente_counter")
    
    def get_next_equip_id(self):
        return self._get_next_id("EQP", "equip_counter")
    
    def get_next_produto_id(self):
        return self._get_next_id("PRD", "produto_counter")
    
    def get_next_tecnico_id(self):
        return self._get_next_id("TEC", "tecnico_counter")
    
    def get_next_os_id(self):
        return self._get_next_id("OS", "os_counter")
    
    # Modifique todos os métodos add_* para usar os novos IDs
    def add_cliente(self, nome, telefone, email, rua, numero, bairro, cidade, estado):
        if not nome or not telefone:
            raise ValueError("Nome e telefone são obrigatórios")
        
        id = self.get_next_cliente_id()
        data_cadastro = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO clientes (id, nome, telefone, email, rua, numero, bairro, cidade, estado, data_cadastro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id, nome, telefone, email, rua, numero, bairro, cidade, estado, data_cadastro))
            self.conn.commit()
            return id
        except Exception as e:
            print(f"Erro ao inserir cliente: {e}")
            self.conn.rollback()
            raise
    
    def add_equipamento(self, cliente_id, tipo, marca, modelo, numero_serie, observacao=None):
        id = self.get_next_equip_id()
        cursor = self.conn.cursor()
        
        # Verificar se a coluna observacao existe, se não, adicionar
        try:
            cursor.execute("SELECT observacao FROM equipamentos LIMIT 1")
        except sqlite3.OperationalError:
            # Adicionar coluna
            cursor.execute("ALTER TABLE equipamentos ADD COLUMN observacao TEXT")
        
        # Inserir equipamento com observação
        cursor.execute('INSERT INTO equipamentos (id, cliente_id, tipo, marca, modelo, numero_serie, observacao) VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (id, cliente_id, tipo, marca, modelo, numero_serie, observacao))
        self.conn.commit()
        return id
    
    def add_produto(self, nome, descricao, preco, quantidade):
        id = self.get_next_produto_id()
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO produtos (id, nome, descricao, preco, quantidade) VALUES (?, ?, ?, ?, ?)',
                     (id, nome, descricao, preco, quantidade))
        self.conn.commit()
        return id
    
    def add_tecnico(self, nome, especialidade):
        id = self.get_next_tecnico_id()
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO tecnicos (id, nome, especialidade) VALUES (?, ?, ?)',
                     (id, nome, especialidade))
        self.conn.commit()
        return id
    
    def add_ordem_servico(self, cliente_id, equipamento_id, tecnico_id, descricao_problema):
        try:
            id = self.get_next_os_id()
            data_abertura = datetime.now().strftime('%d/%m/%Y %H:%M')
            status = 'Aberta'
            cursor = self.conn.cursor()
            print(f"Inserindo OS: {id}, {cliente_id}, {equipamento_id}, {tecnico_id}, {data_abertura}, {status}, {descricao_problema}")
            cursor.execute('INSERT INTO ordens_servico (id, cliente_id, equipamento_id, tecnico_id, data_abertura, status, descricao_problema) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (id, cliente_id, equipamento_id, tecnico_id, data_abertura, status, descricao_problema))
            self.conn.commit()
            return id
        except Exception as e:
            print(f"Erro ao inserir OS: {e}")
            self.conn.rollback()
            raise
    
    def update_status_os(self, os_id, status, descricao_solucao=None):
        cursor = self.conn.cursor()
        if status == 'Fechada':
            # Formato de data brasileiro (dia/mês/ano)
            data_fechamento = datetime.now().strftime('%d/%m/%Y %H:%M')
            cursor.execute('UPDATE ordens_servico SET status = ?, data_fechamento = ?, descricao_solucao = ? WHERE id = ?',
                          (status, data_fechamento, descricao_solucao, os_id))
        else:
            cursor.execute('UPDATE ordens_servico SET status = ? WHERE id = ?', (status, os_id))
        self.conn.commit()

    def buscar_clientes(self, termo_busca=None):
        cursor = self.conn.cursor()
        if termo_busca:
            # Busca por nome, telefone ou email que contenha o termo
            cursor.execute('''
                SELECT id, nome, telefone, email 
                FROM clientes 
                WHERE nome LIKE ? OR telefone LIKE ? OR email LIKE ?
            ''', (f'%{termo_busca}%', f'%{termo_busca}%', f'%{termo_busca}%'))
        else:
            # Retorna todos os clientes (limitados a 20)
            cursor.execute('SELECT id, nome, telefone, email FROM clientes LIMIT 20')
        
        return cursor.fetchall()

    # Adicione este método à classe SistemaOS para buscar equipamentos por cliente
    def buscar_equipamentos_por_cliente(self, cliente_id):
        cursor = self.conn.cursor()
        try:
            # Tenta buscar com a coluna observacao
            cursor.execute('''
                SELECT id, tipo, marca, modelo, numero_serie, observacao
                FROM equipamentos
                WHERE cliente_id = ?
            ''', (cliente_id,))
        except sqlite3.OperationalError:
            # Se falhar, busca sem a coluna (compatibilidade)
            cursor.execute('''
                SELECT id, tipo, marca, modelo, numero_serie
                FROM equipamentos
                WHERE cliente_id = ?
            ''', (cliente_id,))
        return cursor.fetchall()

    # Adicione o método de busca de técnicos na classe SistemaOS
    def buscar_tecnicos(self, termo_busca=None):
        cursor = self.conn.cursor()
        if termo_busca:
            # Busca por nome ou especialidade que contenha o termo
            cursor.execute('''
                SELECT id, nome, especialidade 
                FROM tecnicos 
                WHERE nome LIKE ? OR especialidade LIKE ?
            ''', (f'%{termo_busca}%', f'%{termo_busca}%'))
        else:
            # Retorna todos os técnicos (limitados a 20)
            cursor.execute('SELECT id, nome, especialidade FROM tecnicos LIMIT 20')
        
        return cursor.fetchall()

# Interface com Flet
def main(page: ft.Page):
    page.title = "Sistema de Ordem de Serviço - Eletrônica"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    page.bgcolor = ft.colors.BACKGROUND
    
    # Definindo cores do tema
    primary_color = "#1565C0"  # Azul mais escuro
    secondary_color = "#90CAF9"  # Azul mais claro
    
    # Estilo para botões
    button_style = {
        "bgcolor": primary_color,
        "color": "white",
        "width": 200,
        "height": 45,
        "border_radius": 8
    }
    
    # Estilo para containers
    container_style = {
        "bgcolor": "white",
        "border_radius": 10,
        "padding": 20,
        "margin": 10,
        "shadow": ft.BoxShadow(
            spread_radius=1,
            blur_radius=15,
            color=ft.colors.with_opacity(0.2, "000000"),
            offset=ft.Offset(0, 5),
        )
    }
    
    sistema = SistemaOS()
    
    # Função para exibir mensagens de snackbar (versão atualizada)
    def show_snackbar(page, message):
        snack = ft.SnackBar(
            content=ft.Text(message),
            action="OK"
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
    
    # Adicione esta função para limpar resultados de buscas quando mudar de aba
    def limpar_resultados_busca():
        resultados_busca_os.visible = False
        resultados_busca_os.controls.clear()
        resultados_busca_tecnico.visible = False
        resultados_busca_tecnico.controls.clear()
        page.update()

    # Função para alternar entre telas
    def change_tab(e):
        index = e.control.selected_index
        titulo_pagina.value = ["Cadastro de Clientes", "Cadastro de Equipamentos", 
                             "Cadastro de Produtos", "Cadastro de Técnicos", 
                             "Gerenciamento de OS"][index]
        cliente_container.visible = index == 0
        equipamento_container.visible = index == 1
        produto_container.visible = index == 2
        tecnico_container.visible = index == 3
        os_container.visible = index == 4
        
        # Limpar resultados de busca ao trocar de aba
        limpar_resultados_busca()
        
        page.update()
    
    # Título da página
    titulo_pagina = ft.Text("Cadastro de Clientes", size=24, weight=ft.FontWeight.BOLD, color=primary_color)
    
    # Campos do Cliente (com endereço completo)
    nome_cliente = ft.TextField(label="Nome *", hint_text="Campo obrigatório")
    telefone_cliente = ft.TextField(
        label="Telefone *", 
        hint_text="(DDD) 9XXXX-XXXX",
        helper_text="Formato: (XX) 9XXXX-XXXX",
        prefix_icon=ft.icons.PHONE
    )
    email_cliente = ft.TextField(label="Email")
    rua_cliente = ft.TextField(label="Rua")
    numero_cliente = ft.TextField(label="Número")
    bairro_cliente = ft.TextField(label="Bairro")
    cidade_cliente = ft.TextField(label="Cidade")
    estado_cliente = ft.TextField(label="Estado")
    data_cadastro_text = ft.Text(
        f"Data de Cadastro: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        size=14,
        color=primary_color,
        weight=ft.FontWeight.W_500
    )

    # Campo para buscar cliente no módulo de equipamentos
    busca_cliente_field = ft.TextField(
        label="Buscar Cliente",
        hint_text="Digite nome, telefone ou email",
        prefix_icon=ft.icons.SEARCH,
    )

    # Lista de resultados da busca
    resultados_busca = ft.ListView(
        height=200,
        spacing=2,
        padding=10,
        visible=False,
    )

    # Texto de exibição para cliente selecionado
    cliente_nome_exibicao = ft.Text(
        value="Nenhum cliente selecionado",
        color=ft.colors.GREY_500,
        size=14,
        italic=True
    )

    # Campo oculto para armazenar o ID do cliente
    cliente_id_equip = ft.TextField(
        label="ID do Cliente",
        read_only=True,
        visible=False
    )

    # Função para buscar clientes
    def buscar_cliente(e):
        termo = busca_cliente_field.value
        if not termo or len(termo) < 3:
            resultados_busca.visible = False
            page.update()
            return
            
        resultados = sistema.buscar_clientes(termo)
        resultados_busca.controls.clear()
        
        if not resultados:
            resultados_busca.controls.append(
                ft.Text("Nenhum cliente encontrado", italic=True, color=ft.colors.GREY_500)
            )
        else:
            for cliente in resultados:
                cliente_id, nome, telefone, email = cliente
                resultados_busca.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{nome}", weight=ft.FontWeight.BOLD),
                            ft.Text(f"Tel: {telefone} | Email: {email or 'N/A'}", size=12)
                        ]),
                        margin=5,
                        padding=10,
                        border_radius=5,
                        bgcolor=ft.colors.BLUE_50,
                        data=cliente_id,  # Armazena o ID do cliente como atributo de dados
                        on_click=lambda e: selecionar_cliente(e)
                    )
                )
        
        resultados_busca.visible = True
        page.update()

    # Função para selecionar o cliente quando clicar no resultado
    def selecionar_cliente(e):
        cliente_id = e.control.data
        cliente_nome = e.control.content.controls[0].value
        
        cliente_id_equip.value = cliente_id
        cliente_nome_exibicao.value = f"Cliente selecionado: {cliente_nome}"
        cliente_nome_exibicao.color = primary_color
        cliente_nome_exibicao.italic = False
        
        # Esconde a lista de resultados após a seleção
        resultados_busca.visible = False
        busca_cliente_field.value = ""
        page.update()

    # Associar o evento de mudança ao campo de busca
    busca_cliente_field.on_change = buscar_cliente

    def format_telefone(e):
        # Remove todos os caracteres não numéricos
        text = ''.join(filter(str.isdigit, telefone_cliente.value or ""))
        
        # Formata o número conforme digita
        if len(text) <= 2:
            formatted = text
        elif len(text) <= 7:
            formatted = f"({text[:2]}) {text[2:]}"
        elif len(text) <= 11:
            formatted = f"({text[:2]}) {text[2:7]}-{text[7:]}"
        else:
            formatted = f"({text[:2]}) {text[2:7]}-{text[7:11]}"
            
        # Atualiza o valor do campo
        telefone_cliente.value = formatted
        page.update()

    # Adiciona o evento on_change ao campo de telefone
    telefone_cliente.on_change = format_telefone

    # Atualizar a função add_cliente para usar a nova abordagem
    def add_cliente(e):
        if not nome_cliente.value or not telefone_cliente.value:
            show_snackbar(page, "Nome e telefone são obrigatórios!")
            return
            
        # Extrai apenas os dígitos do telefone para salvar
        telefone_limpo = ''.join(filter(str.isdigit, telefone_cliente.value))
        
        # Valida se o telefone tem o formato correto (DDD + 9 dígitos)
        if len(telefone_limpo) < 11:
            show_snackbar(page, "Telefone deve ter DDD + 9 dígitos")
            return
        
        try:
            sistema.add_cliente(
                nome_cliente.value,
                telefone_limpo,  # Usando a versão limpa para armazenar
                email_cliente.value,
                rua_cliente.value,
                numero_cliente.value,
                bairro_cliente.value,
                cidade_cliente.value,
                estado_cliente.value
            )
            show_snackbar(page, "Cliente cadastrado com sucesso!")
            # Limpa os campos após o cadastro
            for field in [nome_cliente, telefone_cliente, email_cliente, rua_cliente, 
                        numero_cliente, bairro_cliente, cidade_cliente, estado_cliente]:
                field.value = ""
            page.update()
        except Exception as ex:
            show_snackbar(page, f"Erro ao cadastrar: {str(ex)}")
    
    cadastrar_cliente_btn = ft.ElevatedButton(
        "Cadastrar Cliente", 
        on_click=add_cliente,
        style=ft.ButtonStyle(
            bgcolor={"": primary_color},
            color={"": "white"},
            padding=10,
            shape={"": ft.RoundedRectangleBorder(radius=8)}
        )
    )
    
    cliente_container = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Column([
                    nome_cliente,
                    telefone_cliente,
                    email_cliente,
                    data_cadastro_text,  # Adicionando data ao formulário
                ], spacing=15),
                **container_style
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Endereço", size=18, weight=ft.FontWeight.W_500, color=primary_color),
                    rua_cliente,
                    ft.Row([
                        numero_cliente,
                        bairro_cliente,
                    ], spacing=10),
                    ft.Row([
                        cidade_cliente,
                        estado_cliente,
                    ], spacing=10),
                ], spacing=15),
                **container_style
            ),
            ft.Container(
                content=cadastrar_cliente_btn,
                alignment=ft.alignment.center
            ),
        ], spacing=15),
        visible=True,
        padding=20
    )
    
    # Campos do Equipamento - Definições melhoradas
    tipo_equip = ft.TextField(
        label="Tipo de Equipamento *", 
        hint_text="Ex: Notebook, TV, Smartphone...",
        border_color=primary_color,
        focused_border_color=primary_color,
        prefix_icon=ft.icons.DEVICES
    )
    marca_equip = ft.TextField(
        label="Marca", 
        hint_text="Ex: Samsung, LG, Apple...",
        prefix_icon=ft.icons.BRANDING_WATERMARK
    )
    modelo_equip = ft.TextField(
        label="Modelo",
        hint_text="Ex: Galaxy S21, iPhone 13...",
        prefix_icon=ft.icons.MODEL_TRAINING
    )
    numero_serie_equip = ft.TextField(
        label="Número de Série",
        hint_text="Número de série do equipamento",
        prefix_icon=ft.icons.TAG
    )
    observacao_equip = ft.TextField(
        label="Observações",
        hint_text="Condições do equipamento, acessórios, etc",
        multiline=True,
        min_lines=2,
        max_lines=4,
        prefix_icon=ft.icons.NOTES
    )

    # Função para adicionar equipamento melhorada
    def add_equipamento(e):
        if not cliente_id_equip.value:
            show_snackbar(page, "Selecione um cliente primeiro!")
            return
            
        if not tipo_equip.value:
            show_snackbar(page, "O tipo de equipamento é obrigatório!")
            return
        
        try:
            # Adiciona o equipamento ao banco de dados
            equip_id = sistema.add_equipamento(
                cliente_id_equip.value,
                tipo_equip.value,
                marca_equip.value,
                modelo_equip.value,
                numero_serie_equip.value,
                observacao_equip.value  # Novo campo de observações
            )
            
            # Exibe mensagem de sucesso com o ID
            show_snackbar(page, f"Equipamento {equip_id} cadastrado com sucesso!")
            
            # Limpa os campos após o cadastro
            tipo_equip.value = ""
            marca_equip.value = ""
            modelo_equip.value = ""
            numero_serie_equip.value = ""
            observacao_equip.value = ""
            
            # Mantém o cliente selecionado para facilitar cadastros múltiplos
            # Se quiser limpar o cliente também, descomente as linhas abaixo:
            # cliente_id_equip.value = ""
            # cliente_nome_exibicao.value = "Nenhum cliente selecionado"
            # cliente_nome_exibicao.color = ft.colors.GREY_500
            # cliente_nome_exibicao.italic = True
            
            page.update()
        except Exception as ex:
            show_snackbar(page, f"Erro ao cadastrar equipamento: {str(ex)}")
            print(f"Detalhe do erro: {ex}")

    # Container de equipamento redesenhado
    equipamento_container = ft.Container(
        content=ft.Column([
            # Seção de Cliente
            ft.Container(
                content=ft.Column([
                    ft.Text("Selecionar Cliente", 
                        size=18, 
                        weight=ft.FontWeight.W_500, 
                        color=primary_color),
                    busca_cliente_field,
                    resultados_busca,
                    ft.Container(
                        content=ft.Column([
                            cliente_nome_exibicao,
                            ft.Text(f"ID: {cliente_id_equip.value or 'Nenhum'}", size=12, color=ft.colors.GREY_800),
                        ]),
                        bgcolor=ft.colors.BLUE_50,
                        padding=10,
                        border_radius=8,
                        visible=True
                    ),
                    # Mantemos o campo oculto para armazenar o ID
                    ft.Container(content=cliente_id_equip, visible=False)
                ], spacing=10),
                **container_style
            ),
            
            # Seção de Equipamento
            ft.Container(
                content=ft.Column([
                    ft.Text("Dados do Equipamento", 
                        size=18, 
                        weight=ft.FontWeight.W_500, 
                        color=primary_color),
                    
                    # Tipo é obrigatório - destacado com borda
                    ft.Container(
                        content=tipo_equip,
                        border=ft.border.all(1, primary_color),
                        border_radius=8,
                        padding=5
                    ),
                    
                    # Outros campos em grid para melhor aproveitamento
                    ft.Row([
                        ft.Container(content=marca_equip, expand=True),
                        ft.Container(content=modelo_equip, expand=True),
                    ], spacing=10),
                    
                    # Número de série sozinho
                    numero_serie_equip,
                    
                    # Campo de observações
                    observacao_equip,
                    
                    # Botão de cadastro mais destacado
                    ft.Container(
                        content=ft.ElevatedButton(
                            "Cadastrar Equipamento", 
                            on_click=add_equipamento,
                            style=ft.ButtonStyle(
                                bgcolor={"": primary_color},
                                color={"": "white"},
                                padding=15,
                                shape={"": ft.RoundedRectangleBorder(radius=8)},
                                elevation=5
                            ),
                            icon=ft.icons.SAVE
                        ),
                        alignment=ft.alignment.center,
                        margin=ft.margin.only(top=15)
                    )
                ], spacing=15),
                **container_style
            ),
        ], spacing=15),
        visible=False,
        padding=20
    )
    
    # Adicione esta definição antes de usar descricao_problema_os em qualquer container
    # Coloque este código logo após a definição de equipamento_selector

    # Criar o container "sem cliente selecionado"
    sem_cliente_container = ft.Container(
        content=ft.Text(
            "Selecione um cliente para ver seus equipamentos",
            italic=True,
            color=ft.colors.GREY_500
        ),
        visible=True
    )
    sem_cliente_container.id = "sem_cliente_selecionado"  # Configurar o ID desta forma

    # Outros campos da Ordem de Serviço
    descricao_problema_os = ft.TextField(
        label="Descrição do Problema *", 
        hint_text="Descreva o problema relatado pelo cliente",
        multiline=True,
        min_lines=3,
        max_lines=5,
        on_change=lambda e: print(f"Descrição digitada: {e.control.value}"),  # Adicione este callback para depuração
        border_color=ft.colors.RED  # Adicione uma borda vermelha para destacar o campo
    )
    # descricao_problema_os.value = "Teste de descrição"

    # Modificar o equipamento_container_os para incluir o campo descricao_problema_os
    # Crie o objeto Text primeiro
    equip_info_text = ft.Text("", size=12, color=ft.colors.GREY_700)
    equip_info_text.id = "equip_info"

    # Exibição do equipamento selecionado
    equipamento_selector = ft.ListView(
        height=200,
        spacing=2,
        padding=10,
        visible=False,
    )

    equipamento_nome_exibicao = ft.Text(
        value="Nenhum equipamento selecionado",
        color=ft.colors.GREY_500,
        size=14,
        italic=True
    )

    equipamento_id_os = ft.TextField(
        label="ID do Equipamento",
        read_only=True
    )

    equipamento_container_os = ft.Container(
        content=ft.Column([
            ft.Text("Selecionar Equipamento", size=18, weight=ft.FontWeight.W_500, color=primary_color),
            
            # Use a referência existente
            sem_cliente_container,
            
            # Agora equipamento_selector já foi definido
            equipamento_selector,
            
            # Exibição do equipamento selecionado
            ft.Container(
                content=ft.Column([
                    equipamento_nome_exibicao, # Agora esta variável está definida
                    equip_info_text,
                    ft.Container(content=equipamento_id_os, visible=False) # E esta também
                ]),
                bgcolor=ft.colors.BLUE_50,
                padding=10,
                border_radius=8,
                visible=True
            ),
            
            # Descrição do problema, etc.
            ft.Container(
                content=ft.Column([
                    ft.Text("Descrição do Problema *", size=16, weight=ft.FontWeight.W_500, color=ft.colors.RED),
                    descricao_problema_os,
                ]),
                padding=10,
                margin=ft.margin.only(top=10),
                border=ft.border.all(2, color=ft.colors.RED),
                border_radius=8
            ),
        ]),
        **container_style
    )

    # Campos do Produto
    nome_produto = ft.TextField(label="Nome")
    descricao_produto = ft.TextField(label="Descrição")
    preco_produto = ft.TextField(label="Preço", keyboard_type=ft.KeyboardType.NUMBER)
    quantidade_produto = ft.TextField(label="Quantidade", keyboard_type=ft.KeyboardType.NUMBER)
    
    def add_produto(e):
        if not nome_produto.value:
            show_snackbar(page, "Nome do produto é obrigatório!")
            return
        sistema.add_produto(
            nome_produto.value,
            descricao_produto.value,
            float(preco_produto.value) if preco_produto.value else 0.0,
            int(quantidade_produto.value) if quantidade_produto.value else 0
        )
        show_snackbar(page, "Produto cadastrado com sucesso!")
    
    produto_container = ft.Container(
        content=ft.Column([
            nome_produto,
            descricao_produto,
            preco_produto,
            quantidade_produto,
            ft.ElevatedButton("Cadastrar Produto", on_click=add_produto)
        ]),
        visible=False,
        padding=20
    )
    
    # Campos do Técnico
    nome_tecnico = ft.TextField(label="Nome")
    especialidade_tecnico = ft.TextField(label="Especialidade")
    
    def add_tecnico(e):
        if not nome_tecnico.value:
            page.snack_bar = ft.SnackBar(ft.Text("Nome do técnico é obrigatório!"))
            page.snack_bar.open = True
            page.update()
            return
        sistema.add_tecnico(
            nome_tecnico.value,
            especialidade_tecnico.value
        )
        page.snack_bar = ft.SnackBar(ft.Text("Técnico cadastrado com sucesso!"))
        page.snack_bar.open = True
        page.update()
    
    tecnico_container = ft.Container(
        content=ft.Column([
            nome_tecnico,
            especialidade_tecnico,
            ft.ElevatedButton("Cadastrar Técnico", on_click=add_tecnico)
        ]),
        visible=False,
        padding=20
    )
    
    # Modificação do container de OS para incluir busca de cliente

    # Modifique os campos da ordem de serviço para incluir busca
    cliente_id_os = ft.TextField(
        label="ID do Cliente",
        read_only=True,  # Campo somente-leitura, será preenchido pela busca
    )
    cliente_nome_exibicao_os = ft.Text(
        value="Nenhum cliente selecionado",
        color=ft.colors.GREY_500,
        size=14,
        italic=True
    )
    busca_cliente_os = ft.TextField(
        label="Buscar Cliente",
        hint_text="Digite nome, telefone ou ID do cliente",
        prefix_icon=ft.icons.SEARCH,
    )

    # Cria uma lista para mostrar os resultados da busca
    resultados_busca_os = ft.ListView(
        height=200,
        spacing=2,
        padding=10,
        visible=False,
    )

    # Função para realizar a busca quando o usuário digitar
    def buscar_cliente_os(e):
        termo = busca_cliente_os.value
        if not termo or len(termo) < 3:
            resultados_busca_os.visible = False
            page.update()
            return
            
        resultados = sistema.buscar_clientes(termo)
        resultados_busca_os.controls.clear()
        
        if not resultados:
            resultados_busca_os.controls.append(
                ft.Text("Nenhum cliente encontrado", italic=True, color=ft.colors.GREY_500)
            )
        else:
            for cliente in resultados:
                cliente_id, nome, telefone, email = cliente
                resultados_busca_os.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{nome}", weight=ft.FontWeight.BOLD),
                            ft.Text(f"ID: {cliente_id}", size=12),
                            ft.Text(f"Tel: {telefone} | Email: {email or 'N/A'}", size=12)
                        ]),
                        margin=5,
                        padding=10,
                        border_radius=5,
                        bgcolor=ft.colors.BLUE_50,
                        data=cliente_id,  # Armazena o ID do cliente como um atributo de dados
                        on_click=lambda e: selecionar_cliente_os(e)
                    )
                )
        
        resultados_busca_os.visible = True
        page.update()

    # Modificação na função selecionar_cliente_os
    def selecionar_cliente_os(e):
        cliente_id = e.control.data
        cliente_nome = e.control.content.controls[0].value
        
        print(f"Cliente selecionado: ID={cliente_id}, Nome={cliente_nome}")
        
        # Atualiza os campos do cliente
        cliente_id_os.value = cliente_id
        cliente_nome_exibicao_os.value = f"Cliente: {cliente_nome}"
        cliente_nome_exibicao_os.color = primary_color
        cliente_nome_exibicao_os.italic = False
        
        print(f"Valor atribuído ao cliente_id_os: {cliente_id_os.value}")
        
        # Buscar equipamentos do cliente
        equipamentos = sistema.buscar_equipamentos_por_cliente(cliente_id)
        
        # Limpa a seleção anterior de equipamento
        equipamento_id_os.value = ""
        equipamento_selector.visible = False
        equipamento_selector.controls.clear()
        
        # CORREÇÃO AQUI: Em vez de tentar acessar por ID, use a variável sem_cliente_container diretamente
        sem_cliente_container.visible = False
        
        if not equipamentos:
            equipamento_selector.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.WARNING_AMBER, color=ft.colors.AMBER),
                        ft.Text("Este cliente não possui equipamentos cadastrados", 
                              italic=True, color=ft.colors.GREY_700, 
                              text_align=ft.TextAlign.CENTER),
                        ft.Text("Você precisa cadastrar pelo menos um equipamento para criar uma OS",
                              size=12, color=ft.colors.GREY_500,
                              text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    alignment=ft.alignment.center,
                    bgcolor=ft.colors.AMBER_50,
                    border_radius=8
                )
            )
        else:
            for equip in equipamentos:
                # Verifica se temos observações no resultado
                if len(equip) > 5:
                    equip_id, tipo, marca, modelo, num_serie, observacao = equip
                else:
                    equip_id, tipo, marca, modelo, num_serie = equip
                    observacao = None
                    
                # Descrição principal do equipamento
                descricao = f"{tipo} - {marca} {modelo}" if marca and modelo else tipo
                
                # Informações adicionais para exibir na lista
                info_adicional = ""
                if num_serie:
                    info_adicional += f"S/N: {num_serie}"
                
                # Conteúdo do item da lista
                container_content = [
                    ft.Text(descricao, weight=ft.FontWeight.BOLD),
                    ft.Text(info_adicional or "Sem número de série", size=12),
                    ft.Text(f"ID: {equip_id}", size=10, color=ft.colors.GREY_500)
                ]
                
                # Se tiver observação, adiciona
                if observacao:
                    container_content.insert(2, 
                        ft.Text(f"Obs: {observacao[:50]}{'...' if len(observacao) > 50 else ''}", 
                              size=12, color=ft.colors.GREY_700)
                    )
                    
                equipamento_selector.controls.append(
                    ft.Container(
                        content=ft.Column(container_content),
                        margin=5,
                        padding=10,
                        border_radius=5,
                        bgcolor=ft.colors.BLUE_50,
                        data=equip_id,
                        on_click=selecionar_equipamento,
                        ink=True  # Efeito de ondulação ao clicar
                    )
                )
        
        equipamento_selector.visible = True
        
        # Esconde a lista de resultados de clientes após a seleção
        resultados_busca_os.visible = False
        busca_cliente_os.value = ""
        page.update()

    # Função para selecionar um equipamento da lista
    def selecionar_equipamento(e):
        equip_id = e.control.data
        equip_descricao = e.control.content.controls[0].value
        
        # Log para depuração
        print(f"Equipamento selecionado: ID={equip_id}, Descrição={equip_descricao}")
        
        equipamento_id_os.value = equip_id
        equipamento_nome_exibicao.value = f"Equipamento: {equip_descricao}"
        equipamento_nome_exibicao.color = primary_color
        equipamento_nome_exibicao.italic = False
        
        # Verificar se o valor foi atribuído corretamente
        print(f"Valor atribuído ao equipamento_id_os: {equipamento_id_os.value}")
        
        # Esconde a lista de equipamentos
        equipamento_selector.visible = False
        page.update()

    # Busca de equipamentos
    equipamento_id_os = ft.TextField(
        label="ID do Equipamento",
        read_only=True
    )

    # Seleção de equipamento
    equipamento_nome_exibicao = ft.Text(
        value="Nenhum equipamento selecionado",
        color=ft.colors.GREY_500,
        size=14,
        italic=True
    )

    sem_cliente_container = ft.Container(
        content=ft.Text(
            "Selecione um cliente para ver seus equipamentos",
            italic=True,
            color=ft.colors.GREY_500
        ),
        visible=True
    )
    sem_cliente_container.id = "sem_cliente_selecionado"  # Configurar o ID desta forma

    equipamento_container_os = ft.Container(
        content=ft.Column([
            ft.Text("Selecionar Equipamento", size=18, weight=ft.FontWeight.W_500, color=primary_color),
            
            # Use a variável em vez da definição inline
            sem_cliente_container,
            
            # Lista de equipamentos (inicialmente oculta)
            equipamento_selector,
            
            # Resto do código...
        ]),
        **container_style
    )

    # No módulo de OS, vamos adicionar campos para exibir as datas
    data_abertura_text = ft.Text(
        f"Data de Abertura: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        size=14, 
        color=primary_color,
        weight=ft.FontWeight.W_500
    )

    # Outros campos da Ordem de Serviço que também parecem faltar
    tecnico_id_os = ft.TextField(
        label="ID do Técnico *",
        hint_text="ID do técnico é obrigatório"
    )
    status_os = ft.Dropdown(
        label="Status",
        options=[
            ft.dropdown.Option("Aberta"),
            ft.dropdown.Option("Em andamento"),
            ft.dropdown.Option("Aguardando peças"),
            ft.dropdown.Option("Fechada")
        ],
        value="Aberta"
    )
    descricao_solucao_os = ft.TextField(
        label="Descrição da Solução",
        multiline=True,
        min_lines=3,
        max_lines=5
    )

    # Campo para busca de técnicos
    busca_tecnico_os = ft.TextField(
        label="Buscar Técnico",
        hint_text="Digite nome ou especialidade do técnico",
        prefix_icon=ft.icons.SEARCH,
    )

    # Container para mostrar resultados da busca
    resultados_busca_tecnico = ft.ListView(
        height=200,
        spacing=2,
        padding=10,
        visible=False,
    )

    # Texto de exibição para técnico selecionado
    tecnico_nome_exibicao = ft.Text(
        value="Nenhum técnico selecionado",
        color=ft.colors.GREY_500,
        size=14,
        italic=True
    )

    # Função para buscar técnicos
    def buscar_tecnico(e):
        termo = busca_tecnico_os.value
        if not termo or len(termo) < 3:
            resultados_busca_tecnico.visible = False
            page.update()
            return
            
        resultados = sistema.buscar_tecnicos(termo)
        resultados_busca_tecnico.controls.clear()
        
        if not resultados:
            resultados_busca_tecnico.controls.append(
                ft.Text("Nenhum técnico encontrado", italic=True, color=ft.colors.GREY_500)
            )
        else:
            for tecnico in resultados:
                tecnico_id, nome, especialidade = tecnico
                resultados_busca_tecnico.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"{nome}", weight=ft.FontWeight.BOLD),
                            ft.Text(f"Especialidade: {especialidade or 'N/A'}", size=12),
                            ft.Text(f"ID: {tecnico_id}", size=12)
                        ]),
                        margin=5,
                        padding=10,
                        border_radius=5,
                        bgcolor=ft.colors.BLUE_50,
                        data=tecnico_id,  # Armazena o ID do técnico como um atributo de dados
                        on_click=lambda e: selecionar_tecnico(e)
                    )
                )
        
        resultados_busca_tecnico.visible = True
        page.update()

    # Função para selecionar o técnico
    def selecionar_tecnico(e):
        tecnico_id = e.control.data
        tecnico_nome = e.control.content.controls[0].value
        
        tecnico_id_os.value = tecnico_id
        tecnico_nome_exibicao.value = f"Técnico selecionado: {tecnico_nome}"
        tecnico_nome_exibicao.color = primary_color
        tecnico_nome_exibicao.italic = False
        
        # Esconde a lista de resultados após a seleção
        resultados_busca_tecnico.visible = False
        busca_tecnico_os.value = ""
        page.update()

    # Associa o evento de mudança ao campo de busca
    busca_tecnico_os.on_change = buscar_tecnico

    # Adicionar esta linha após a definição de busca_cliente_os (linha ~950)
    busca_cliente_os.on_change = buscar_cliente_os

    # Verificar se esta linha existe na linha ~1070 (se não, adicione)
    busca_tecnico_os.on_change = buscar_tecnico

    # Funções para OS
    def add_os(e):
        # Primeiro, atualize explicitamente o valor
        page.update()
        
        # Depuração detalhada
        print("----- VERIFICAÇÃO DE DESCRIÇÃO -----")
        print(f"Descrição ID: {id(descricao_problema_os)}")
        print(f"Valor atual: '{descricao_problema_os.value}'")
        print(f"Tipo: {type(descricao_problema_os.value)}")
        
        # Pegue o valor digitado novamente diretamente do campo
        atual_descricao = descricao_problema_os.value
        
        # Verifica se todos os campos estão preenchidos
        if not cliente_id_os.value:
            show_snackbar(page, "Selecione um cliente!")
            return
                
        if not equipamento_id_os.value:
            show_snackbar(page, "Selecione um equipamento!")
            return
        
        if not tecnico_id_os.value:
            show_snackbar(page, "Selecione um técnico!")
            return
        
        # Na função add_os, comente a validação para testar se é o único problema:
        # if atual_descricao is None or atual_descricao.strip() == "":
        #     show_snackbar(page, "Descrição do problema é obrigatória!")
        #     return
        
        try:
            # Criação da OS após validação bem-sucedida
            os_id = sistema.add_ordem_servico(
                cliente_id_os.value,
                equipamento_id_os.value,
                tecnico_id_os.value,
                atual_descricao.strip()  # Usar a variável já processada
            )
            show_snackbar(page, f"Ordem de Serviço #{os_id} criada com sucesso!")
            
            # Limpa os campos após cadastrar
            cliente_id_os.value = ""
            equipamento_id_os.value = ""
            tecnico_id_os.value = ""
            descricao_problema_os.value = ""
            
            # Reseta os textos de exibição
            cliente_nome_exibicao_os.value = "Nenhum cliente selecionado"
            cliente_nome_exibicao_os.color = ft.colors.GREY_500
            cliente_nome_exibicao_os.italic = True
            
            equipamento_nome_exibicao.value = "Nenhum equipamento selecionado"
            equipamento_nome_exibicao.color = ft.colors.GREY_500
            equipamento_nome_exibicao.italic = True
            
            tecnico_nome_exibicao.value = "Nenhum técnico selecionado"
            tecnico_nome_exibicao.color = ft.colors.GREY_500
            tecnico_nome_exibicao.italic = True
            
            # Atualiza a data mostrada
            atualizar_datas()
            page.update()
        except Exception as ex:
            show_snackbar(page, f"Erro ao criar OS: {str(ex)}")
            # Imprimir erro para depuração
            print(f"Detalhes do erro: {ex}")

    def update_os(e):
        # Verificações de campos obrigatórios
        if not cliente_id_os.value:
            show_snackbar(page, "Selecione uma OS para atualizar!")
            return
        
        if not equipamento_id_os.value:
            show_snackbar(page, "Equipamento é obrigatório!")
            return
        
        if not status_os.value:
            show_snackbar(page, "Selecione um status!")
            return
            
        # Se o status for "Fechada", descrição da solução é obrigatória
        if status_os.value == "Fechada" and (descricao_solucao_os.value is None or descricao_solucao_os.value.strip() == ""):
            show_snackbar(page, "Descrição da solução é obrigatória para fechar uma OS!")
            return
            
        try:
            sistema.update_status_os(
                cliente_id_os.value,  # Idealmente, você teria um campo separado para o ID da OS
                status_os.value,
                descricao_solucao_os.value
            )
            show_snackbar(page, "Status da OS atualizado com sucesso!")
            
            # Se a OS foi fechada, limpa os campos
            if status_os.value == "Fechada":
                # Limpa os campos
                cliente_id_os.value = ""
                equipamento_id_os.value = ""
                tecnico_id_os.value = ""
                descricao_problema_os.value = ""
                descricao_solucao_os.value = ""
                status_os.value = "Aberta"
                
                # Reseta os textos de exibição
                cliente_nome_exibicao_os.value = "Nenhum cliente selecionado"
                cliente_nome_exibicao_os.color = ft.colors.GREY_500
                cliente_nome_exibicao_os.italic = True
                
                equipamento_nome_exibicao.value = "Nenhum equipamento selecionado"
                equipamento_nome_exibicao.color = ft.colors.GREY_500
                equipamento_nome_exibicao.italic = True

                tecnico_nome_exibicao.value = "Nenhum técnico selecionado"
                tecnico_nome_exibicao.color = ft.colors.GREY_500
                tecnico_nome_exibicao.italic = True
                
                # Atualiza a data
                atualizar_datas()
                
        except Exception as ex:
            show_snackbar(page, f"Erro ao atualizar status: {str(ex)}")

    def atualizar_datas():
        """
        Update date fields in the OS form with current date/time.
        Can be called when creating a new OS or refreshing the form.
        """
        current_datetime = datetime.now().strftime('%d/%m/%Y %H:%M')
        data_abertura_text.value = f"Data de Abertura: {current_datetime}"
        # If you have other date fields, update them here too
        # For example:
        # data_atualizacao_text.value = f"Última Atualização: {current_datetime}"
        page.update()

    # Adicione esta função para depurar os campos de ID
    def verificar_ids(e):
        print("---- STATUS DOS IDs ----")
        print(f"Cliente ID: '{cliente_id_os.value}'")
        print(f"Equipamento ID: '{equipamento_id_os.value}'")
        print(f"Técnico ID: '{tecnico_id_os.value}'")
        print(f"Descrição: '{descricao_problema_os.value}'")
        
        if cliente_id_os.value and equipamento_id_os.value and tecnico_id_os.value and descricao_problema_os.value:
            print("TODOS OS CAMPOS ESTÃO PREENCHIDOS!")
        else:
            print("CAMPOS FALTANDO:")
            if not cliente_id_os.value:
                print("- Cliente ID está vazio")
            if not equipamento_id_os.value:
                print("- Equipamento ID está vazio")
            if not tecnico_id_os.value:
                print("- Técnico ID está vazio")
            if not descricao_problema_os.value:
                print("- Descrição está vazia")

    os_container = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("Buscar e Selecionar Cliente", size=18, weight=ft.FontWeight.W_500, color=primary_color),
                    busca_cliente_os,
                    resultados_busca_os,
                    cliente_nome_exibicao_os,
                    cliente_id_os,
                    data_abertura_text,  # Adicionado aqui para garantir que seja incluído
                ]),
                **container_style
            ),
            equipamento_container_os,
            ft.Container(
                content=ft.Column([
                    ft.Text("Selecionar Técnico", size=18, weight=ft.FontWeight.W_500, color=primary_color),
                    busca_tecnico_os,
                    resultados_busca_tecnico,
                    ft.Container(  # Container para exibir o técnico selecionado
                        content=ft.Column([
                            tecnico_nome_exibicao,
                            ft.Text(f"ID: ", size=12, color=ft.colors.GREY_800, 
                                spans=[ft.TextSpan(
                                    text=tecnico_id_os.value or "Nenhum", 
                                    style=ft.TextStyle(color=ft.colors.GREY_800)
                                )]
                            ),
                        ]),
                        bgcolor=ft.colors.BLUE_50,
                        padding=10,
                        border_radius=8,
                        visible=True
                    ),
                    tecnico_id_os,  # Deixe visível para debugging ou use read_only=True
                ]),
                **container_style
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Status da OS", size=18, weight=ft.FontWeight.W_500, color=primary_color),
                    status_os,
                    descricao_solucao_os,
                ]),
                **container_style
            ),
            ft.Container(
                content=ft.Row([
                    ft.ElevatedButton(
                        "Criar OS", 
                        on_click=add_os,
                        style=ft.ButtonStyle(
                            bgcolor={"": primary_color},
                            color={"": "white"},
                            padding=10,
                            shape={"": ft.RoundedRectangleBorder(radius=8)}
                        )
                    ),
                    ft.ElevatedButton(
                        "Atualizar Status", 
                        on_click=update_os,
                        style=ft.ButtonStyle(
                            bgcolor={"": secondary_color},
                            color={"": primary_color},
                            padding=10,
                            shape={"": ft.RoundedRectangleBorder(radius=8)}
                        )
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                **container_style
            ),
            ft.Container(
                content=ft.ElevatedButton(
                    "Verificar IDs", 
                    on_click=verificar_ids,
                    style=ft.ButtonStyle(
                        bgcolor={"": ft.colors.AMBER},
                        color={"": "black"},
                        padding=10
                    )
                ),
                alignment=ft.alignment.center
            ),
            # Adicione um botão específico que force o valor:
            ft.ElevatedButton(
                "Definir Descrição Teste", 
                on_click=lambda e: definir_descricao_teste()
            )
        ]),
        visible=False,
        padding=20
    )

    def definir_descricao_teste():
        descricao_problema_os.value = "TESTE DESCRIÇÃO FORÇADA"
        print(f"Valor definido: {descricao_problema_os.value}")
        page.update()

    # Barra de navegação
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.PERSON, label="Clientes"),
            ft.NavigationBarDestination(icon=ft.icons.DEVICES, label="Equipamentos"),
            ft.NavigationBarDestination(icon=ft.icons.INVENTORY, label="Produtos"),
            ft.NavigationBarDestination(icon=ft.icons.ENGINEERING, label="Técnicos"),
            ft.NavigationBarDestination(icon=ft.icons.WORK, label="OS")
        ],
        on_change=change_tab,
        bgcolor=primary_color,
        selected_index=0,
        indicator_color=secondary_color,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        height=65
    )
    
    # Adiciona cabeçalho e containers à página
    page.add(
        ft.Container(
            content=ft.Row([titulo_pagina], alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.padding.only(top=20, bottom=10)
        ),
        ft.Container(
            content=ft.Column([
                cliente_container,
                equipamento_container,
                produto_container,
                tecnico_container,
                os_container
            ], scroll=ft.ScrollMode.AUTO),
            expand=True
        )
    )

# Iniciar a aplicação
if __name__ == "__main__":
    ft.app(target=main)
