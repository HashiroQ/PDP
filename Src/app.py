from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///documents.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)

class DocumentType(db.Model):
    __tablename__ = 'document_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    documents = db.relationship('Document', backref='type', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120))
    documents = db.relationship('Document', backref='employee', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('document_types.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    operations = db.relationship('Operation', backref='document', lazy=True,
                                cascade="all, delete-orphan")

class Operation(db.Model):
    __tablename__ = 'operations'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    operation_type = db.Column(db.String(3), nullable=False)  # 'in' / 'out'
    product = db.relationship('Product', backref='operations')

def recalc_product_quantity(product_id):
    """ Пересчитывает quantity по всем операциям прихода/расхода """
    product = Product.query.get(product_id)
    if not product:
        return
    in_total = db.session.query(db.func.sum(Operation.quantity)).filter(
        Operation.product_id == product_id,
        Operation.operation_type == 'in'
    ).scalar() or 0
    out_total = db.session.query(db.func.sum(Operation.quantity)).filter(
        Operation.product_id == product_id,
        Operation.operation_type == 'out'
    ).scalar() or 0
    product.quantity = in_total - out_total
    db.session.commit()

def apply_operations(operations_data, doc):
    """ Создаёт/обновляет операции документа и корректирует остатки """
    if doc.id:
        old_product_ids = {op.product_id for op in doc.operations}
        Operation.query.filter_by(document_id=doc.id).delete()
        db.session.flush()
    new_product_ids = set()
    for op_data in operations_data:
        op = Operation(
            document_id=doc.id if doc.id else None,
            product_id=op_data['product_id'],
            quantity=op_data['quantity'],
            operation_type=op_data['operation_type']
        )
        db.session.add(op)
        new_product_ids.add(op_data['product_id'])
    db.session.flush()

    all_product_ids = new_product_ids
    if doc.id:
        all_product_ids |= old_product_ids
    for pid in all_product_ids:
        recalc_product_quantity(pid)

@app.route('/api/documenttypes', methods=['GET', 'POST'])
def handle_document_types():
    if request.method == 'GET':
        types = DocumentType.query.all()
        return jsonify([{'id': t.id, 'name': t.name} for t in types])
    elif request.method == 'POST':
        data = request.json
        dt = DocumentType(name=data['name'])
        db.session.add(dt)
        db.session.commit()
        return jsonify({'id': dt.id, 'name': dt.name}), 201

@app.route('/api/documenttypes/<int:id>', methods=['PUT', 'DELETE'])
def modify_document_type(id):
    dt = DocumentType.query.get_or_404(id)
    if request.method == 'PUT':
        dt.name = request.json['name']
        db.session.commit()
        return jsonify({'id': dt.id, 'name': dt.name})
    elif request.method == 'DELETE':
        db.session.delete(dt)
        db.session.commit()
        return '', 204


@app.route('/api/employees', methods=['GET', 'POST'])
def handle_employees():
    if request.method == 'GET':
        emps = Employee.query.all()
        return jsonify([{'id': e.id, 'name': e.name, 'position': e.position} for e in emps])
    data = request.json
    emp = Employee(name=data['name'], position=data.get('position', ''))
    db.session.add(emp)
    db.session.commit()
    return jsonify({'id': emp.id, 'name': emp.name, 'position': emp.position}), 201

@app.route('/api/employees/<int:id>', methods=['PUT', 'DELETE'])
def modify_employee(id):
    emp = Employee.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.json
        emp.name = data['name']
        emp.position = data.get('position', '')
        db.session.commit()
        return jsonify({'id': emp.id, 'name': emp.name, 'position': emp.position})
    db.session.delete(emp)
    db.session.commit()
    return '', 204

@app.route('/api/products', methods=['GET', 'POST'])
def handle_products():
    if request.method == 'GET':
        prods = Product.query.all()
        return jsonify([{'id': p.id, 'name': p.name, 'quantity': p.quantity} for p in prods])
    data = request.json
    prod = Product(name=data['name'], quantity=0)  
    db.session.add(prod)
    db.session.commit()
    return jsonify({'id': prod.id, 'name': prod.name, 'quantity': prod.quantity}), 201

@app.route('/api/products/<int:id>', methods=['PUT', 'DELETE'])
def modify_product(id):
    prod = Product.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.json
        prod.name = data['name']
        db.session.commit()
        return jsonify({'id': prod.id, 'name': prod.name, 'quantity': prod.quantity})
    db.session.delete(prod)
    db.session.commit()
    return '', 204

@app.route('/api/documents', methods=['GET', 'POST'])
def handle_documents():
    if request.method == 'GET':
        docs = Document.query.all()
        result = []
        for d in docs:
            result.append({
                'id': d.id,
                'number': d.number,
                'date': d.date.isoformat(),
                'type': d.type.name if d.type else '',
                'employee': d.employee.name if d.employee else '',
                'operations_count': len(d.operations)
            })
        return jsonify(result)

    data = request.json
    doc = Document(
        number=data['number'],
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        type_id=data['type_id'],
        employee_id=data['employee_id']
    )
    db.session.add(doc)
    db.session.flush() 
    apply_operations(data.get('operations', []), doc)
    db.session.commit()
    return jsonify({'id': doc.id, 'message': 'Created'}), 201

@app.route('/api/documents/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def modify_document(id):
    doc = Document.query.get_or_404(id)
    if request.method == 'GET':
        ops = []
        for op in doc.operations:
            ops.append({
                'id': op.id,
                'product_id': op.product_id,
                'product_name': op.product.name,
                'quantity': op.quantity,
                'operation_type': op.operation_type
            })
        return jsonify({
            'id': doc.id,
            'number': doc.number,
            'date': doc.date.isoformat(),
            'type_id': doc.type_id,
            'employee_id': doc.employee_id,
            'operations': ops
        })

    elif request.method == 'PUT':
        data = request.json
        doc.number = data['number']
        doc.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        doc.type_id = data['type_id']
        doc.employee_id = data['employee_id']
        apply_operations(data.get('operations', []), doc)
        db.session.commit()
        return jsonify({'message': 'Updated'})

    elif request.method == 'DELETE':
        product_ids = {op.product_id for op in doc.operations}
        db.session.delete(doc)
        db.session.commit()
        for pid in product_ids:
            recalc_product_quantity(pid)
        return '', 204

# ------------------------- ЗАПУСК -------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not DocumentType.query.first():
            db.session.add(DocumentType(name='Приходная накладная'))
            db.session.add(DocumentType(name='Расходная накладная'))
            db.session.commit()
    app.run(debug=True, port=5000)