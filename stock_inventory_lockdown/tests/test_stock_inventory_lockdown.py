# -*- coding: utf-8 -*-
# © 2014 Acsone SA/NV (http://www.acsone.eu)
# © 2016 Numérigraphe SARL
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.addons.stock.tests.common import TestStockCommon


class StockInventoryLocationTest(TestStockCommon):
    def setUp(self):
        super(StockInventoryLocationTest, self).setUp()
        # Make a new location with a parent and a child.
        self.new_parent_location = self.env['stock.location'].create(
            {'name': 'Test parent location',
             'usage': 'internal'})
        self.new_location = self.env['stock.location'].create(
            {'name': 'Test location',
             'usage': 'internal',
             'location_id': self.new_parent_location.id})
        self.new_sublocation = self.env['stock.location'].create(
            {'name': 'Test sublocation',
             'usage': 'internal',
             'location_id': self.new_location.id})
        # Input goods
        self.env['stock.quant'].create(
            {'location_id': self.new_location.id,
             'product_id': self.productA.id,
             'qty': 10.0})
        self.env['stock.quant'].create(
            {'location_id': self.new_parent_location.id,
             'product_id': self.productB.id,
             'qty': 5.0})
        # Prepare an inventory
        self.inventory = self.env['stock.inventory'].create(
            {'name': 'Lock down location',
             'filter': 'none',
             'location_id': self.new_location.id})
        self.inventory.prepare_inventory()
        self.assertTrue(self.inventory.line_ids, 'The inventory is empty.')

    def create_stock_move(self, product, origin_id=False, dest_id=False):
        return self.env['stock.move'].create({
            'name': 'Test move lock down',
            'product_id': product.id,
            'product_uom_qty': 10.0,
            'product_uom': product.uom_id.id,
            'location_id': origin_id or self.supplier_location,
            'location_dest_id': dest_id or self.customer_location,
        })

    def test_update_parent_location(self):
        """Updating the parent of a location is OK if no inv. in progress."""
        self.inventory.action_cancel_draft()
        self.inventory.location_id.location_id = self.env.ref(
            'stock.stock_location_4')

    def test_update_parent_location_locked_down(self):
        """Updating the parent of a location must fail"""
        with self.assertRaises(ValidationError):
            self.inventory.location_id.location_id = self.env.ref(
                'stock.stock_location_4')

    def test_inventory(self):
        """We must still be able to finish the inventory"""
        self.assertTrue(self.inventory.line_ids)
        self.inventory.line_ids.write({'product_qty': 42.0})
        for line in self.inventory.line_ids:
            self.assertNotEqual(line.product_id.with_context(
                location=line.location_id.id).qty_available, 42.0)
        self.inventory.action_done()
        for line in self.inventory.line_ids:
            self.assertEqual(line.product_id.with_context(
                location=line.location_id.id).qty_available, 42.0)

    def test_inventory_sublocation(self):
        """We must be able to make an inventory in a sublocation"""
        inventory_subloc = self.env['stock.inventory'].create(
            {'name': 'Lock down location',
             'filter': 'partial',
             'location_id': self.new_sublocation.id})
        inventory_subloc.prepare_inventory()
        line = self.env['stock.inventory.line'].create(
            {'product_id': self.productA.id,
             'product_qty': 22.0,
             'location_id': self.new_sublocation.id,
             'inventory_id': inventory_subloc.id})
        self.assertTrue(inventory_subloc.line_ids)
        inventory_subloc.action_done()
        self.assertEqual(line.product_id.with_context(
            location=line.location_id.id).qty_available, 22.0)

    def test_move(self):
        """Stock moves must be forbidden during inventory from/to inventoried
        location."""
        move1 = self.create_stock_move(
            self.productA, origin_id=self.inventory.location_id.id)
        move1.action_confirm()
        with self.assertRaises(ValidationError):
            move1.action_assign()
            move1.action_done()
        move2 = self.create_stock_move(
            self.productA, dest_id=self.inventory.location_id.id)
        with self.assertRaises(ValidationError):
            move2.action_confirm()
            move2.action_assign()
            move2.action_done()

    def test_move_reserved_quants(self):
        """Shipping stock should be allowed or not depending on reserved
        quants' locations.
        * move1: quants are fetched from the parent location.
        * move2: quants are fetched from 'new location' which is being
        inventoried."""
        move1 = self.create_stock_move(
            self.productB, self.new_parent_location.id)
        move1.action_confirm()
        move1.action_assign()
        move1.action_done()
        self.assertEqual(
            move1.state, 'done', 'Move has not been completed')
        move2 = self.create_stock_move(
            self.productA, self.new_parent_location.id)
        move2.action_confirm()
        with self.assertRaises(ValidationError):
            move2.action_assign()
            move2.action_done()
