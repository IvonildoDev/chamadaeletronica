import sqlite3
import flet as ft
from datetime import datetime
import uuid
from fpdf import FPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

# Nova importação
import fpdf

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
        try:
            cursor.execute('INSERT INTO equipamentos (id, cliente_id, tipo, marca, modelo, numero_serie, observacao) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (id, cliente_id, tipo, marca, modelo, numero_serie, observacao))
            self.conn.commit()
            return id
        except Exception as ex:
            show_snackbar(page, f"Erro ao cadastrar equipamento: {str(ex)}")
            print(f"Detalhe do erro: {ex}")  # <-- Corrigido aqui
    
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
            # Primeiro tenta buscar pelo ID exato (se for um ID)
            cursor.execute('SELECT id, nome, telefone, email, rua, numero, bairro, cidade, estado FROM clientes WHERE id = ?', (termo_busca,))
            result = cursor.fetchall()
            
            # Se não encontrou pelo ID, busca nos outros campos
            if not result:
                cursor.execute('''
                    SELECT id, nome, telefone, email, rua, numero, bairro, cidade, estado
                    FROM clientes 
                    WHERE nome LIKE ? OR telefone LIKE ? OR email LIKE ?
                ''', (f'%{termo_busca}%', f'%{termo_busca}%', f'%{termo_busca}%'))
                result = cursor.fetchall()
                
            return result
        else:
            # Retorna todos os clientes (limitados a 20)
            cursor.execute('SELECT id, nome, telefone, email, rua, numero, bairro, cidade, estado FROM clientes LIMIT 20')
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

    # Adicione este método à classe SistemaOS para buscar ordens de serviço
    def buscar_ordens_servico(self, filtro=None):
        """
        Busca ordens de serviço com filtro por ID da OS ou nome do cliente
        """
        cursor = self.conn.cursor()
        
        if filtro:
            # Busca por ID da OS ou por nome de cliente
            cursor.execute('''
                SELECT os.id, os.cliente_id, os.equipamento_id, os.tecnico_id, 
                      os.data_abertura, os.data_fechamento, os.status, 
                      os.descricao_problema, os.descricao_solucao,
                      c.nome, c.telefone, c.email, c.rua, c.numero, c.bairro, c.cidade, c.estado,
                      e.tipo, e.marca, e.modelo, e.numero_serie, e.observacao,
                      t.nome as tecnico_nome, t.especialidade
                FROM ordens_servico os
                JOIN clientes c ON os.cliente_id = c.id
                JOIN equipamentos e ON os.equipamento_id = e.id
                JOIN tecnicos t ON os.tecnico_id = t.id
                WHERE os.id LIKE ? OR c.nome LIKE ?
                ORDER BY os.data_abertura DESC
            ''', (f'%{filtro}%', f'%{filtro}%'))
        else:
            # Retorna todas as ordens (limitadas a 50)
            cursor.execute('''
                SELECT os.id, os.cliente_id, os.equipamento_id, os.tecnico_id, 
                      os.data_abertura, os.data_fechamento, os.status, 
                      os.descricao_problema, os.descricao_solucao,
                      c.nome, c.telefone, c.email, c.rua, c.numero, c.bairro, c.cidade, c.estado,
                      e.tipo, e.marca, e.modelo, e.numero_serie, e.observacao,
                      t.nome as tecnico_nome, t.especialidade
                FROM ordens_servico os
                JOIN clientes c ON os.cliente_id = c.id
                JOIN equipamentos e ON os.equipamento_id = e.id
                JOIN tecnicos t ON os.tecnico_id = t.id
                ORDER BY os.data_abertura DESC
                LIMIT 50
            ''')
        
        return cursor.fetchall()

# Modifique a função gerar_pdf_os
def gerar_pdf_os(cliente, equipamento, descricao, nome_tecnico):
    # Cria pasta 'OS' se não existir
    os_folder = "OS"
    if not os.path.exists(os_folder):
        os.makedirs(os_folder)
        print(f"Pasta '{os_folder}' criada com sucesso!")
    
    # Definir nome do arquivo dentro da pasta OS
    filename = os.path.join(os_folder, f"os_{cliente['nome']}_{equipamento['tipo']}.pdf".replace(" ", "_"))
    
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Resto do código permanece igual...

    c.save()
    show_snackbar(page, f"PDF gerado: {filename}")

# Modifique a função gerar_pdf_os_existente
def gerar_pdf_os_existente(os_data):
    """Gera PDF para uma OS existente com design melhorado"""
    
    # Importar o módulo os com um nome diferente para evitar conflito com o parâmetro
    import os as os_module
    
    # Cria pasta 'OS' se não existir
    os_folder = "OS"
    if not os_module.path.exists(os_folder):
        os_module.makedirs(os_folder)
        print(f"Pasta '{os_folder}' criada com sucesso!")
    
    # Extrair os dados necessários
    (os_id, cliente_id, equipamento_id, tecnico_id, 
     data_abertura, data_fechamento, status, 
     descricao_problema, descricao_solucao,
     cliente_nome, telefone, email, rua, numero, bairro, cidade, estado,
     tipo_equip, marca, modelo, num_serie, observacao,
     tecnico_nome, especialidade) = os_data
    
    # Nome do arquivo com data para evitar sobrescrita
    data_hora = datetime.now().strftime('%Y%m%d_%H%M')
    filename = os_module.path.join(os_folder, f"os_{os_id}_{cliente_nome.replace(' ', '_')}_{data_hora}.pdf".replace(" ", "_"))
    
    print(f"Gerando PDF em: {os_module.path.abspath(filename)}")
    
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Resto do código permanece igual...

    c.save()
    show_snackbar(page, f"PDF gerado: {filename}")

    # Também substitua todas as outras ocorrências de 'os.' por 'os_module.'
    # Por exemplo, ao abrir o PDF automaticamente:
    try:
        if platform.system() == 'Darwin':       # macOS
            subprocess.call(('open', filename))
        elif platform.system() == 'Windows':    # Windows
            os_module.startfile(filename)
        else:                                   # linux
            subprocess.call(('xdg-open', filename))
    except Exception as e:
        print(f"Erro ao abrir PDF: {e}")

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
        titulo_pagina.value = [
            "Cadastro de Clientes", 
            "Cadastro de Equipamentos", 
            "Cadastro de Produtos", 
            "Cadastro de Técnicos", 
            "Gerenciamento de OS",
            "Listagem de Ordens de Serviço"  # Novo título
        ][index]
        
        cliente_container.visible = index == 0
        equipamento_container.visible = index == 1
        produto_container.visible = index == 2
        tecnico_container.visible = index == 3
        os_container.visible = index == 4
        lista_os_container.visible = index == 5  # Nova visibilidade
        
        # Se selecionou Listar OS, carrega todas as ordens
        if index == 5:
            buscar_os(None)  # Carrega OS automaticamente
        
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
                # Use os mesmos 9 campos retornados pela consulta SQL
                cliente_id, nome, telefone, email, rua, numero, bairro, cidade, estado = cliente
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
        label="Descrição do Problema", # Remova o asterisco "*"
        hint_text="Descreva o problema relatado pelo cliente (opcional)",
        multiline=True,
        min_lines=3,
        max_lines=5,
        on_change=lambda e: print(f"Descrição digitada: {e.control.value}"),
        border_color=ft.colors.GREY_400,  # Cor neutra em vez de vermelho
        bgcolor=ft.colors.GREY_50   # Fundo neutro em vez de vermelho
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
                    ft.Text("Descrição do Problema", size=16, weight=ft.FontWeight.W_500, color=ft.colors.GREY_800), # Remova o asterisco e mude a cor
                    descricao_problema_os,
                ]),
                padding=10,
                margin=ft.margin.only(top=10),
                border=ft.border.all(1, color=ft.colors.GREY_400), # Borda neutra
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
                # Desempacote todos os campos corretamente
                cliente_id, nome, telefone, email, rua, numero, bairro, cidade, estado = cliente
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

    # Variável para armazenar temporariamente os dados da OS
    os_dados_salvos = {}

    def salvar_os(e):
        # Salva os valores atuais dos campos em um dicionário
        os_dados_salvos["cliente_id"] = cliente_id_os.value
        os_dados_salvos["equipamento_id"] = equipamento_id_os.value
        os_dados_salvos["tecnico_id"] = tecnico_id_os.value
        os_dados_salvos["descricao"] = descricao_problema_os.value
        show_snackbar(page, f"OS salva temporariamente!\nDescrição: {descricao_problema_os.value}")
        print(f"DEBUG salvar_os: {os_dados_salvos}")

    # Funções para OS
    def add_os(e):
        print("----- VERIFICAÇÃO DE DESCRIÇÃO -----")
        print(f"Descrição ID: {id(descricao_problema_os)}")
        print(f"Valor atual: '{descricao_problema_os.value}'")
        print(f"Tipo: {type(descricao_problema_os.value)}")
        
        # Pegue o valor digitado diretamente do campo
        atual_descricao = descricao_problema_os.value or ""  # Use string vazia se for None
        
        # Verifica apenas campos que continuam obrigatórios
        if not cliente_id_os.value:
            show_snackbar(page, "Selecione um cliente!")
            return
                
        if not equipamento_id_os.value:
            show_snackbar(page, "Selecione um equipamento!")
            return
        
        if not tecnico_id_os.value:
            show_snackbar(page, "Selecione um técnico!")
            return
        
        try:
            # PRIMEIRO: Busque os dados de cliente e equipamento para o modal
            # Procura cliente
            resultados_cliente = sistema.buscar_clientes(cliente_id_os.value)
            if not resultados_cliente:
                show_snackbar(page, "Cliente não encontrado!")
                return
            cliente = resultados_cliente[0]
            
            # Busca equipamentos
            equipamento_lista = sistema.buscar_equipamentos_por_cliente(cliente_id_os.value)
            equipamento = next((eq for eq in equipamento_lista if eq[0] == equipamento_id_os.value), None)
            if not equipamento:
                show_snackbar(page, "Equipamento não encontrado!")
                return
            
            # Dados do técnico
            tecnico_nome = tecnico_nome_exibicao.value.replace("Técnico selecionado: ", "")
            
            # Prepara dicionários para modal e PDF
            cliente_dict = {
                "nome": cliente[1],
                "telefone": cliente[2],
                "email": cliente[3] or "N/A",
                "rua": cliente[4] or "",
                "numero": cliente[5] or "",
                "bairro": cliente[6] or "",
                "cidade": cliente[7] or "",
                "estado": cliente[8] or ""
            }
            
            # Campos do equipamento com tratamento para evitar None
            equipamento_dict = {
                "tipo": equipamento[1] or "",
                "marca": equipamento[2] or "",
                "modelo": equipamento[3] or "",
                "numero_serie": equipamento[4] or "",
                "observacao": equipamento[5] if len(equipamento) > 5 else ""
            }
            
            # --- Modal ---
            def gerar_pdf_e_salvar(ev):
                # Criação da OS no banco
                os_id = sistema.add_ordem_servico(
                    cliente_id_os.value,
                    equipamento_id_os.value,
                    tecnico_id_os.value,
                    atual_descricao.strip()
                )
                
                # Gera o PDF
                gerar_pdf_os(cliente_dict, equipamento_dict, atual_descricao, tecnico_nome)
                
                # Fecha o modal
                dlg.open = False
                
                # Mostra confirmação
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

            modal_content = ft.Column([
                ft.Text("Confirmação da OS e Termo de Garantia", size=20, weight=ft.FontWeight.BOLD, color=primary_color),
                ft.Divider(),
                ft.Text(f"Cliente: {cliente_dict['nome']}"),
                ft.Text(f"Telefone: {cliente_dict['telefone']}"),
                ft.Text(f"Email: {cliente_dict['email']}"),
                ft.Text(f"Endereço: {cliente_dict['rua']}, {cliente_dict['numero']} - {cliente_dict['bairro']}, {cliente_dict['cidade']}/{cliente_dict['estado']}"),
                ft.Divider(),
                ft.Text(f"Equipamento: {equipamento_dict['tipo']} - {equipamento_dict['marca']} {equipamento_dict['modelo']}"),
                ft.Text(f"Nº Série: {equipamento_dict['numero_serie']}"),
                ft.Text(f"Observações: {equipamento_dict['observacao']}"),
                ft.Divider(),
                ft.Text(f"Problema relatado: {atual_descricao}"),
                ft.Divider(),
                ft.Text("Termo: O cliente tem o prazo de 90 (noventa) dias, a contar da data de notificação de conclusão do serviço, para retirar o equipamento. Após este prazo, o equipamento poderá ser descartado ou vendido para cobrir custos, conforme legislação vigente.", size=12, italic=True, color=ft.colors.RED),
                ft.Divider(),
                ft.Text("Assinatura do Cliente: ___________________________", size=14),
                ft.Text("Assinatura do Representante: _____________________", size=14),
                ft.Text(f"Técnico responsável: {tecnico_nome}", size=12),
            ], scroll=ft.ScrollMode.AUTO, width=500, height=400)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Revisar e Gerar PDF da OS"),
                content=modal_content,
                actions=[
                    ft.TextButton("Gerar PDF e Salvar", on_click=gerar_pdf_e_salvar, style=ft.ButtonStyle(color=primary_color)),
                    ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg, 'open', False) or page.update()),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dlg)
            dlg.open = True
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
        
        # O resto da função continua normalmente...
        # Por exemplo:
        show_snackbar(page, f"PDF gerado: {filename}")

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
                        "Salvar OS",
                        on_click=salvar_os,
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.colors.AMBER},
                            color={"": "black"},
                            padding=10,
                            shape={"": ft.RoundedRectangleBorder(radius=8)}
                        )
                    ),
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

    # def definir_descricao_teste():
    #     descricao_problema_os.value = "TESTE DESCRIÇÃO FORÇADA"
    #     print(f"Valor definido para descrição: {descricao_problema_os.value}")
    #     print(f"ID do campo: {id(descricao_problema_os)}")
    #     page.update()

    # Adicione os elementos para listar ordens de serviço
    busca_os_field = ft.TextField(
        label="Buscar Ordens de Serviço",
        hint_text="Digite o ID da OS ou nome do cliente",
        prefix_icon=ft.icons.SEARCH,
        width=400
    )

    lista_os = ft.ListView(
        height=400,
        spacing=10,
        padding=20,
        auto_scroll=True
    )

    os_detalhes = ft.Container(
        content=ft.Column([
            ft.Text("Selecione uma OS para ver os detalhes", 
                   size=16, 
                   color=ft.colors.GREY_500,
                   italic=True),
        ]),
        padding=20,
        bgcolor=ft.colors.WHITE,
        border_radius=10,
        border=ft.border.all(1, ft.colors.GREY_300),
        margin=10,
        visible=True
    )

    # Adicione a função para buscar as ordens de serviço
    def buscar_os(e):
        termo = busca_os_field.value
        
        # Limpa a lista atual
        lista_os.controls.clear()
        
        # Faz a busca no banco de dados
        ordens = sistema.buscar_ordens_servico(termo)
        
        if not ordens:
            lista_os.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF, color=ft.colors.GREY_500, size=40),
                        ft.Text("Nenhuma ordem de serviço encontrada", 
                              italic=True, 
                              color=ft.colors.GREY_500)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    alignment=ft.alignment.center
                )
            )
        else:
            for ordem in ordens:
                # Desempacotamos os valores de cada OS
                (os_id, cliente_id, equipamento_id, tecnico_id, 
                 data_abertura, data_fechamento, status, 
                 descricao_problema, descricao_solucao,
                 cliente_nome, telefone, email, rua, numero, bairro, cidade, estado,
                 tipo_equip, marca, modelo, num_serie, observacao,
                 tecnico_nome, especialidade) = ordem
                
                # Data de fechamento formatada
                fechamento_txt = f"Fechada em: {data_fechamento}" if data_fechamento else "Em aberto"
                
                # Status com cores diferentes
                status_color = {
                    "Aberta": ft.colors.BLUE,
                    "Em andamento": ft.colors.ORANGE,
                    "Aguardando peças": ft.colors.PURPLE,
                    "Fechada": ft.colors.GREEN,
                }.get(status, ft.colors.GREY)
                
                # Descrição curta do problema
                problema_curto = (descricao_problema[:50] + "...") if descricao_problema and len(descricao_problema) > 50 else (descricao_problema or "Sem descrição")
                
                # Container para cada OS
                lista_os.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"OS: {os_id}", 
                                      weight=ft.FontWeight.BOLD, 
                                      size=16),
                                ft.Text(status, 
                                      weight=ft.FontWeight.BOLD, 
                                      color=status_color)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            
                            ft.Divider(height=1, color=ft.colors.GREY_300),
                            
                            ft.Row([
                                ft.Column([
                                    ft.Text("Cliente:", size=12, color=ft.colors.GREY_700),
                                    ft.Text(cliente_nome, weight=ft.FontWeight.BOLD)
                                ], expand=True),
                                
                                ft.Column([
                                    ft.Text("Equipamento:", size=12, color=ft.colors.GREY_700),
                                    ft.Text(f"{tipo_equip} {marca} {modelo}".strip())
                                ], expand=True)
                            ]),
                            
                            ft.Row([
                                ft.Column([
                                    ft.Text("Abertura:", size=12, color=ft.colors.GREY_700),
                                    ft.Text(data_abertura)
                                ], expand=True),
                                
                                ft.Column([
                                    ft.Text("Fechamento:", size=12, color=ft.colors.GREY_700),
                                    ft.Text(data_fechamento or "Em aberto")
                                ], expand=True),
                            ]),
                            
                            ft.Text("Problema: " + problema_curto, 
                                  size=12, 
                                  color=ft.colors.GREY_800,
                                  italic=True)
                        ]),
                        bgcolor=ft.colors.WHITE,
                        border=ft.border.all(1, ft.colors.GREY_300),
                        border_radius=10,
                        padding=15,
                        margin=5,
                        ink=True,  # Efeito de ondulação ao clicar
                        data=ordem,  # Armazena todos os dados da OS
                        on_click=exibir_detalhes_os
                    )
                )
        
        page.update()

    # Função para mostrar detalhes quando clicar em uma OS
    def exibir_detalhes_os(e):
        os_data = e.control.data
        
        # Desempacotamos os valores
        (os_id, cliente_id, equipamento_id, tecnico_id, 
         data_abertura, data_fechamento, status, 
         descricao_problema, descricao_solucao,
         cliente_nome, telefone, email, rua, numero, bairro, cidade, estado,
         tipo_equip, marca, modelo, num_serie, observacao,
         tecnico_nome, especialidade) = os_data
        
        # Criamos o conteúdo do modal
        modal_content = ft.Column([
            # Cabeçalho da OS com status
            ft.Row([
                ft.Text(f"Ordem de Serviço: {os_id}", 
                       size=20, 
                       weight=ft.FontWeight.BOLD,
                       color=primary_color),
                ft.Container(
                    content=ft.Text(status, color="white"),
                    bgcolor={
                        "Aberta": ft.colors.BLUE,
                        "Em andamento": ft.colors.ORANGE,
                        "Aguardando peças": ft.colors.PURPLE,
                        "Fechada": ft.colors.GREEN,
                    }.get(status, ft.colors.GREY),
                    border_radius=15,
                    padding=ft.padding.only(left=10, right=10, top=5, bottom=5),
                    width=150,
                    alignment=ft.alignment.center
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # Datas
            ft.Row([
                ft.Text(f"Aberta em: {data_abertura}", size=14),
                ft.Text(f"Fechada em: {data_fechamento or 'Em aberto'}", size=14),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Divider(height=1),
            
            # Dados do Cliente
            ft.Container(
                content=ft.Column([
                    ft.Text("Dados do Cliente", 
                           size=16, 
                           weight=ft.FontWeight.BOLD,
                           color=primary_color),
                    ft.Text(f"Nome: {cliente_nome}", size=14),
                    ft.Text(f"Telefone: {telefone}", size=14),
                    ft.Text(f"Email: {email or 'N/A'}", size=14),
                    ft.Text(f"Endereço: {rua}, {numero} - {bairro}, {cidade}/{estado}", size=14),
                ]),
                bgcolor=ft.colors.BLUE_50,
                border_radius=10,
                padding=15,
                margin=ft.margin.only(top=10, bottom=10)
            ),
            
            # Dados do Equipamento
            ft.Container(
                content=ft.Column([
                    ft.Text("Dados do Equipamento", 
                           size=16, 
                           weight=ft.FontWeight.BOLD,
                           color=primary_color),
                    ft.Text(f"Tipo: {tipo_equip}", size=14),
                    ft.Text(f"Marca/Modelo: {marca} {modelo}", size=14),
                    ft.Text(f"Número de Série: {num_serie or 'N/A'}", size=14),
                    ft.Text(f"Observações: {observacao or 'N/A'}", size=14),
                ]),
                bgcolor=ft.colors.GREEN_50,
                border_radius=10,
                padding=15,
                margin=ft.margin.only(top=10, bottom=10)
            ),
            
            # Dados do Técnico
            ft.Container(
                content=ft.Column([
                    ft.Text("Técnico Responsável", 
                           size=16, 
                           weight=ft.FontWeight.BOLD,
                           color=primary_color),
                    ft.Text(f"Nome: {tecnico_nome}", size=14),
                    ft.Text(f"Especialidade: {especialidade or 'N/A'}", size=14),
                ]),
                bgcolor=ft.colors.AMBER_50,
                border_radius=10,
                padding=15,
                margin=ft.margin.only(top=10, bottom=10)
            ),
            
            # Problema relatado
            ft.Text("Descrição do Problema:", 
                   size=16, 
                   weight=ft.FontWeight.BOLD,
                   color=primary_color),
            ft.Container(
                content=ft.Text(descricao_problema or "Não informado"),
                bgcolor=ft.colors.RED_50,
                width=float("inf"),
                padding=10,
                border_radius=5
            ),
            
            # Solução aplicada
            ft.Text("Solução Aplicada:", 
                   size=16, 
                   weight=ft.FontWeight.BOLD,
                   color=primary_color),
            ft.Container(
                content=ft.Text(descricao_solucao or "OS não finalizada"),
                bgcolor=ft.colors.GREEN_50,
                width=float("inf"),
                padding=10,
                border_radius=5
            ),
        ], scroll=ft.ScrollMode.AUTO)
        
        # Criar botões para o modal
        modal_actions = [
            ft.ElevatedButton(
                "Imprimir OS",
                icon=ft.icons.PRINT,
                on_click=lambda _: gerar_pdf_os_existente(os_data),
                style=ft.ButtonStyle(
                    bgcolor={"": primary_color},
                    color={"": "white"},
                )
            ),
            ft.ElevatedButton(
                "Editar OS",
                icon=ft.icons.EDIT,
                on_click=lambda _: fechar_modal_e_editar(os_data),
                style=ft.ButtonStyle(
                    bgcolor={"": ft.colors.AMBER},
                    color={"": "black"},
                )
            ),
            ft.TextButton("Fechar", on_click=lambda _: close_dlg())
        ]
        
        # Criando a função para fechar o modal
        def close_dlg():
            dlg_modal.open = False
            page.update()
        
        # Função para fechar o modal e editar
        def fechar_modal_e_editar(data):
            close_dlg()
            editar_os(data)
        
        # Criar o modal
        dlg_modal = ft.AlertDialog(
            title=ft.Text("Detalhes da Ordem de Serviço", size=20, weight=ft.FontWeight.BOLD),
            content=modal_content,
            actions=modal_actions,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        # Mostrar o modal
        page.overlay.append(dlg_modal)
        dlg_modal.open = True
        page.update()

    # Função para gerar PDF de uma OS existente
    def gerar_pdf_os_existente(os_data):
        """Gera PDF para uma OS existente com design melhorado"""
        
        # Importar o módulo os com um nome diferente para evitar conflito com o parâmetro
        import os as os_module
        
        # Cria pasta 'OS' se não existir
        os_folder = "OS"
        if not os_module.path.exists(os_folder):
            os_module.makedirs(os_folder)
            print(f"Pasta '{os_folder}' criada com sucesso!")
        
        # Extrair os dados necessários
        (os_id, cliente_id, equipamento_id, tecnico_id, 
         data_abertura, data_fechamento, status, 
         descricao_problema, descricao_solucao,
         cliente_nome, telefone, email, rua, numero, bairro, cidade, estado,
         tipo_equip, marca, modelo, num_serie, observacao,
         tecnico_nome, especialidade) = os_data
        
        # Nome do arquivo com data para evitar sobrescrita
        data_hora = datetime.now().strftime('%Y%m%d_%H%M')
        filename = os_module.path.join(os_folder, f"os_{os_id}_{cliente_nome.replace(' ', '_')}_{data_hora}.pdf".replace(" ", "_"))
        
        print(f"Gerando PDF em: {os_module.path.abspath(filename)}")
        
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter  # width=612, height=792 pontos
        
        # Adicionar borda à página (mais fina e sutil)
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(1)
        c.rect(20, 20, width-40, height-40)
        
        # Cabeçalho com informações da empresa - TAMANHO REDUZIDO
        c.setFont("Helvetica-Bold", 16)  # Reduzido de 18 para 16
        c.drawCentredString(width/2, height-50, "ELETRÔNICA NEW STAR")  # Posição ajustada de -60 para -50
        
        c.setFont("Helvetica", 10)  # Reduzido de 12 para 10
        c.drawCentredString(width/2, height-70, "CNPJ: 07.914.206/0001-76")  # Posição ajustada
        c.drawCentredString(width/2, height-85, "Rua Sete de Maio, 559 A - Chã do Pilar")
        c.drawCentredString(width/2, height-100, "Pilar - AL, CEP: 57150-000 - Tel: (82) 9999-9999")
        
        # Linha separadora
        c.setLineWidth(0.5)  # Linha mais fina
        c.line(50, height-115, width-50, height-115)
        
        # Título do documento
        c.setFont("Helvetica-Bold", 14)  # Reduzido de 16 para 14
        c.drawCentredString(width/2, height-140, f"ORDEM DE SERVIÇO #{os_id}")
        
        # Status da OS com design melhorado
        status_colors = {
            "Aberta": (0, 0, 0.8),  # Azul
            "Em andamento": (0.9, 0.5, 0),  # Laranja
            "Aguardando peças": (0.6, 0, 0.6),  # Roxo
            "Fechada": (0, 0.6, 0),  # Verde
        }
        color = status_colors.get(status, (0.5, 0.5, 0.5))  # Cinza como padrão
        
        # Caixa para o status mais compacta
        c.setFillColorRGB(*color)
        c.setStrokeColorRGB(*color)
        c.roundRect(width/2-50, height-165, 100, 20, 8, fill=1)  # Menor e mais acima
        c.setFillColorRGB(1, 1, 1)  # Branco
        c.setFont("Helvetica-Bold", 12)  # Fonte menor
        c.drawCentredString(width/2, height-155, status.upper())
        c.setFillColorRGB(0, 0, 0)  # Preto
        
        # Datas - Posicionamento ajustado
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height-190, "Abertura:")
        c.setFont("Helvetica", 10)
        c.drawString(110, height-190, data_abertura)
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(width-250, height-190, "Fechamento:")
        c.setFont("Helvetica", 10)
        c.drawString(width-170, height-190, data_fechamento or "Em aberto")
        
        # Linha separadora
        c.line(50, height-200, width-50, height-200)
        
        # Dados do Cliente - Layout mais compacto
        y = height-220
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "INFORMAÇÕES DO CLIENTE")
        y -= 15
        
        # Tabela de informações do cliente em duas colunas
        col1_x = 50
        col2_x = width/2
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Nome:")
        c.setFont("Helvetica", 10)
        c.drawString(col1_x + 50, y, cliente_nome)
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col2_x, y, "Telefone:")
        c.setFont("Helvetica", 10)
        c.drawString(col2_x + 60, y, telefone)
        y -= 15
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Email:")
        c.setFont("Helvetica", 10)
        c.drawString(col1_x + 50, y, email or "N/A")
        y -= 15
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Endereço:")
        c.setFont("Helvetica", 10)
        endereco = f"{rua}, {numero} - {bairro}, {cidade}/{estado}"
        # Verificar se o endereço é muito longo
        if len(endereco) > 50:
            c.drawString(col1_x + 60, y, endereco[:50])
            c.drawString(col1_x + 60, y - 12, endereco[50:])
            y -= 12  # Espaço adicional se endereço for longo
        else:
            c.drawString(col1_x + 60, y, endereco)
        y -= 20
        
        # Dados do Equipamento - Layout melhorado
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "INFORMAÇÕES DO EQUIPAMENTO")
        y -= 15
        
        # Tabela de informações do equipamento em duas colunas
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Tipo:")
        c.setFont("Helvetica", 10)
        c.drawString(col1_x + 50, y, tipo_equip or "")
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col2_x, y, "Marca/Modelo:")
        c.setFont("Helvetica", 10)
        c.drawString(col2_x + 80, y, f"{marca} {modelo}".strip())
        y -= 15
        
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Nº Série:")
        c.setFont("Helvetica", 10)
        c.drawString(col1_x + 50, y, num_serie or "Não informado")
        y -= 15
        
        # Observações do equipamento com quebra de linha se for muito longo
        c.setFont("Helvetica-Bold", 10)
        c.drawString(col1_x, y, "Observações:")
        c.setFont("Helvetica", 10)
        obs = observacao or "Nenhuma"
        if len(obs) > 70:
            c.drawString(col1_x + 75, y, obs[:70])
            c.drawString(col1_x + 75, y - 12, obs[70:140])
            y -= 12  # Espaço adicional
        else:
            c.drawString(col1_x + 75, y, obs)
        y -= 20
        
        # Descrição do problema
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "DESCRIÇÃO DO PROBLEMA")
        y -= 15
        
        # Caixa para o problema - mais compacta
        c.setFillColorRGB(0.95, 0.95, 1.0)  # Azul bem claro
        c.setStrokeColorRGB(0.8, 0.8, 0.9)
        problema_height = 50  # Reduzido de 60 para 50
        c.rect(50, y-problema_height, width-100, problema_height, fill=1)
        c.setFillColorRGB(0, 0, 0)  # Preto
        
        # Texto do problema
        textobject = c.beginText(55, y-12)
        textobject.setFont("Helvetica", 10)  # Fonte menor
        if descricao_problema:
            # Dividir em linhas se for muito longo
            lines = []
            for line in descricao_problema.split('\n'):
                if len(line) > 80:  # Permite linhas um pouco mais longas
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line) + len(word) + 1 <= 80:
                            current_line += (" " + word if current_line else word)
                        else:
                            lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                else:
                    lines.append(line)
            
            for line in lines[:4]:  # Limitar a 4 linhas
                textobject.textLine(line)
        else:
            textobject.textLine("Não informado")
        
        c.drawText(textobject)
        y -= problema_height + 5
        
        # Se existir solução, mostrá-la
        if status == "Fechada" and descricao_solucao:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "SOLUÇÃO APLICADA")
            y -= 15
            
            # Caixa para a solução - também mais compacta
            c.setFillColorRGB(0.95, 1.0, 0.95)  # Verde bem claro
            c.setStrokeColorRGB(0.8, 0.9, 0.8)
            solucao_height = 50  # Altura reduzida
            c.rect(50, y-solucao_height, width-100, solucao_height, fill=1)
            c.setFillColorRGB(0, 0, 0)  # Preto
            
            # Texto da solução
            textobject = c.beginText(55, y-12)
            textobject.setFont("Helvetica", 10)  # Fonte menor
            
            # Mesmo processamento para o texto da solução
            lines = []
            for line in descricao_solucao.split('\n'):
                if len(line) > 80:
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line) + len(word) + 1 <= 80:
                            current_line += (" " + word if current_line else word)
                        else:
                            lines.append(current_line)
                            current_line = word
                    if current_line:
                        lines.append(current_line)
                else:
                    lines.append(line)
            
            for line in lines[:4]:  # Limitar a 4 linhas
                textobject.textLine(line)
            
            c.drawText(textobject)
            y -= solucao_height + 5
        
        # Técnico responsável
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Técnico Responsável:")
        c.setFont("Helvetica", 10)
        c.drawString(160, y, tecnico_nome)
        
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(160, y-12, f"Especialidade: {especialidade or 'N/A'}")
        y -= 25
        
        # Termo de garantia em destaque - MAIS COMPACTO
        c.setFont("Helvetica-Bold", 11)  # Reduzido
        c.drawString(50, y, "TERMO DE GARANTIA")
        y -= 15
        
        # Texto do termo de garantia melhorado - FONTE MENOR
        termo_garantia = """
1. PRAZO: Garantimos os serviços por 90 dias, conforme Código de Defesa do Consumidor.
2. COBERTURA: Esta garantia cobre apenas componentes substituídos e serviços descritos nesta OS.
3. EXCLUSÕES: Não cobre: a) Uso inadequado; b) Quedas/umidade; c) Oscilações elétricas; d) Outros problemas.
4. RETIRADA: Prazo de 90 dias para retirada após conclusão. Após, sujeito a descarte conforme lei.
        """
        
        # Caixa para o termo de garantia - MENOR ALTURA
        c.setFillColorRGB(1.0, 0.98, 0.9)  # Amarelo bem claro
        c.setStrokeColorRGB(0.9, 0.8, 0.7)
        termo_height = 70  # Reduzido
        c.rect(50, y-termo_height, width-100, termo_height, fill=1)
        c.setFillColorRGB(0, 0, 0)  # Preto
        
        # Texto do termo
        textobject = c.beginText(55, y-12)
        textobject.setFont("Helvetica", 8)  # Fonte menor
        for line in termo_garantia.split('\n'):
            if line.strip():  # Só adiciona linhas não vazias
                textobject.textLine(line)
        c.drawText(textobject)
        y -= termo_height + 10
        
        # Assinaturas - ESPAÇAMENTO ADEQUADO PARA EVITAR SOBREPOSIÇÃO
        assinatura_y = max(100, y-20)  # Garante espaço mínimo ou usa a posição calculada
        
        c.setFont("Helvetica", 10)
        c.line(100, assinatura_y, 250, assinatura_y)
        c.drawCentredString(175, assinatura_y-15, "Assinatura do Cliente")
        
        c.line(350, assinatura_y, 500, assinatura_y)
        c.drawCentredString(425, assinatura_y-15, "Assinatura do Representante")
        
        # Carimbo da empresa
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.circle(175, assinatura_y-65, 30, stroke=1)  # Carimbo menor
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(175, assinatura_y-60, "CARIMBO")
        c.drawCentredString(175, assinatura_y-72, "DA EMPRESA")
        
        # Rodapé
        c.setFont("Helvetica-Oblique", 7)  # Fonte ainda menor
        c.drawCentredString(width/2, 35, f"Ordem de Serviço #{os_id} gerada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        c.drawCentredString(width/2, 25, "Este documento é um comprovante oficial de serviço - ELETRÔNICA NEW STAR")
        
        # Adicione isso ao final da função gerar_pdf_os_existente antes de c.save()
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, 100, f"Versão atualizada: {datetime.now()}")

        c.save()
        show_snackbar(page, f"PDF da OS {os_id} gerado: {filename}")
        
        # Imprimir informação para debug
        print(f"PDF salvo em: {os_module.path.abspath(filename)}")
        
        # Abrir o PDF automaticamente
        import platform, subprocess
        try:
            if platform.system() == 'Darwin':       # macOS
                subprocess.call(('open', filename))
            elif platform.system() == 'Windows':    # Windows
                os_module.startfile(filename)
            else:                                   # linux
                subprocess.call(('xdg-open', filename))
        except Exception as e:
            print(f"Erro ao abrir PDF: {e}")

    # Associe a função de busca ao campo
    busca_os_field.on_change = buscar_os

    # Adicione a função buscar_todas_os
    def buscar_todas_os():
        busca_os_field.value = ""
        buscar_os(None)
        page.update()

    # Crie o container para listar ordens de serviço
    lista_os_container = ft.Container(
        content=ft.Column([
            ft.Text("Listar Ordens de Serviço", size=24, weight=ft.FontWeight.BOLD, color=primary_color),
            ft.Row([
                busca_os_field,
                ft.ElevatedButton(
                    "Buscar", 
                    icon=ft.icons.SEARCH,
                    on_click=lambda _: buscar_os(None),
                    style=ft.ButtonStyle(
                        bgcolor={"": primary_color},
                        color={"": "white"},
                    )
                ),
                ft.ElevatedButton(
                    "Mostrar Todas",
                    on_click=lambda _: buscar_todas_os(),
                    style=ft.ButtonStyle(
                        bgcolor={"": secondary_color},
                        color={"": "black"},
                    )
                )
            ], alignment=ft.MainAxisAlignment.CENTER),
            
            # Split view para lista e detalhes
            ft.Row([
                # Lista de OS
                ft.Container(
                    content=lista_os,
                    bgcolor=ft.colors.BLUE_50,
                    border_radius=10,
                    expand=3
                ),
                
                # Detalhes da OS
                os_detalhes
            ], expand=True, spacing=10),
            
        ]),
        visible=False,
        padding=20,
    )

    # Barra de navegação
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.PERSON, label="Clientes"),
            ft.NavigationBarDestination(icon=ft.icons.DEVICES, label="Equipamentos"),
            ft.NavigationBarDestination(icon=ft.icons.INVENTORY, label="Produtos"),
            ft.NavigationBarDestination(icon=ft.icons.ENGINEERING, label="Técnicos"),
            ft.NavigationBarDestination(icon=ft.icons.WORK, label="OS"),
            ft.NavigationBarDestination(icon=ft.icons.LIST_ALT, label="Listar OS")  # Nova opção
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
                os_container,
                lista_os_container  # Novo container
            ], scroll=ft.ScrollMode.AUTO),
            expand=True
        )
    )

# Iniciar a aplicação
if __name__ == "__main__":
    ft.app(target=main)
