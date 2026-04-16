"""Seed the database with initial production plan data."""
from sqlalchemy.orm import Session
from datetime import date

from app.database import engine, SessionLocal, Base
from app.models import Product, ProductType, Supplier, Inventory, BOM


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def seed_data():
    """Insert initial seed data for the simulation."""
    db = SessionLocal()
    
    try:
        # Check if already seeded
        if db.query(Product).first():
            print("Database already seeded.")
            return
        
        # Define products (raw materials and finished goods)
        raw_materials = [
            Product(name="kit_piezas", type=ProductType.RAW.value),
            Product(name="pcb", type=ProductType.RAW.value),
            Product(name="CTRL-V2", type=ProductType.RAW.value),
            Product(name="CTRL-V3", type=ProductType.RAW.value),
            Product(name="extrusor", type=ProductType.RAW.value),
            Product(name="sensor_autonivel", type=ProductType.RAW.value),
            Product(name="cables_conexion", type=ProductType.RAW.value),
            Product(name="transformador_24v", type=ProductType.RAW.value),
            Product(name="enchufe_schuko", type=ProductType.RAW.value),
        ]
        
        finished_products = [
            Product(name="P3D-Classic", type=ProductType.FINISHED.value),
            Product(name="P3D-Pro", type=ProductType.FINISHED.value),
        ]
        
        all_products = raw_materials + finished_products
        for product in all_products:
            db.add(product)
        db.commit()
        
        # Update IDs after commit
        products = {p.name: p for p in db.query(Product).all()}
        
        # Create suppliers
        suppliers = [
            Supplier(
                name="ComponentSupplier-EU",
                product_id=products["kit_piezas"].id,
                unit_cost=150.0,
                lead_time_days=3
            ),
            Supplier(
                name="ElectroParts-China",
                product_id=products["pcb"].id,
                unit_cost=25.0,
                lead_time_days=14
            ),
            Supplier(
                name="ElectronicsHub-EU",
                product_id=products["CTRL-V2"].id,
                unit_cost=45.0,
                lead_time_days=5
            ),
            Supplier(
                name="ElectronicsHub-EU",
                product_id=products["CTRL-V3"].id,
                unit_cost=55.0,
                lead_time_days=5
            ),
            Supplier(
                name="MechComponents-EU",
                product_id=products["extrusor"].id,
                unit_cost=80.0,
                lead_time_days=7
            ),
            Supplier(
                name="SensorsWorld-US",
                product_id=products["sensor_autonivel"].id,
                unit_cost=35.0,
                lead_time_days=10
            ),
            Supplier(
                name="CableMfg-Asia",
                product_id=products["cables_conexion"].id,
                unit_cost=8.0,
                lead_time_days=12
            ),
            Supplier(
                name="PowerSupply-EU",
                product_id=products["transformador_24v"].id,
                unit_cost=22.0,
                lead_time_days=4
            ),
            Supplier(
                name="AccessoriesGlobal",
                product_id=products["enchufe_schuko"].id,
                unit_cost=5.0,
                lead_time_days=6
            ),
        ]
        
        for supplier in suppliers:
            db.add(supplier)
        
        # Initialize inventory with starting stock
        inventories = [
            Inventory(product_id=products["kit_piezas"].id, quantity=30),
            Inventory(product_id=products["pcb"].id, quantity=50),
            Inventory(product_id=products["CTRL-V2"].id, quantity=20),
            Inventory(product_id=products["CTRL-V3"].id, quantity=15),
            Inventory(product_id=products["extrusor"].id, quantity=25),
            Inventory(product_id=products["sensor_autonivel"].id, quantity=10),
            Inventory(product_id=products["cables_conexion"].id, quantity=100),
            Inventory(product_id=products["transformador_24v"].id, quantity=40),
            Inventory(product_id=products["enchufe_schuko"].id, quantity=50),
        ]
        
        for inv in inventories:
            db.add(inv)
        
        # Bill of Materials for P3D-Classic
        bom_classic = [
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["kit_piezas"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["pcb"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["CTRL-V2"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["extrusor"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["cables_conexion"].id, quantity=2),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["transformador_24v"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Classic"].id, material_id=products["enchufe_schuko"].id, quantity=1),
        ]
        
        # Bill of Materials for P3D-Pro
        bom_pro = [
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["kit_piezas"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["pcb"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["CTRL-V3"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["extrusor"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["sensor_autonivel"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["cables_conexion"].id, quantity=3),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["transformador_24v"].id, quantity=1),
            BOM(finished_product_id=products["P3D-Pro"].id, material_id=products["enchufe_schuko"].id, quantity=1),
        ]
        
        for bom in bom_classic + bom_pro:
            db.add(bom)
        
        db.commit()
        print("✓ Database seeded successfully!")
        print(f"  - {len(all_products)} products")
        print(f"  - {len(suppliers)} suppliers")
        print(f"  - Inventory initialized")
        print(f"  - BOM configured for P3D-Classic and P3D-Pro")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    seed_data()
