# coding=utf-8

from odoo import api, fields, models, exceptions
from odoo.addons import decimal_precision as dp
from odoo import api, fields, models, SUPERUSER_ID, _

#from ..scenter.purchase_order import PurchaseOrderDao


class PurchaseOrder(models.Model):
    _name = "purchase.order"
    _inherit = ['purchase.order']
    _finish_func = 'approval_finish'

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        # 'refuse': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    # slug = fields.Char('平台关联slug')
    state = fields.Selection(selection_add=[])

    #submit_btn_show = fields.Boolean('是否显示提交审批按钮', compute='_compute_submit_btn_show')
    #approval_button_show = fields.Boolean('是否显示审批按钮', compute='_compute_approval_btn_show')
    #approval_log_show = fields.Boolean('是否显示审批记录按钮', compute='_compute_approval_log_show')

    @api.model
    def _is_use_platform(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        po_2_platform = ICPSudo.get_param('srm_purchase.po_2_platform', default=False)
        return po_2_platform

    # 
    # def button_approve(self, force=False):
    #     self.write({'state': 'pending', 'date_approve': fields.Date.context_today(self)})
    #     self.action_push_2_platform()
    #     return {}

    
    # def button_cancel(self):
    #     super(PurchaseOrder, self).button_cancel()
    #     if self.slug and self._is_use_platform():
    #         PurchaseOrderDao(self.env).update(self.slug, {'state': 'cancel'})

    
#     def button_unlock(self):
#         super(PurchaseOrder, self).button_unlock()
#         if self.slug and self._is_use_platform():
#             PurchaseOrderDao(self.env).update(self.slug, {'state': 'purchase'})

    
    def action_submit(self):
        self.create_approval_workflow()
        self.write({'state': 'to approve'})
        return True

    
    def _ship_create_picking(self, vals):
        self.ensure_one()
        StockPicking = self.env['stock.picking']
        order = self
        if any([ptype in ['product', 'consu'] for ptype in order.order_line.mapped('product_id.type')]):
            res = order._prepare_picking()
            picking = StockPicking.create(res)
            moves = order.order_line._create_stock_moves(picking, vals)
            moves = moves.filtered(lambda x: x.state not in ('done', 'cancel'))._action_confirm()
            seq = 0
            for move in sorted(moves, key=lambda move: move.date):
                seq += 5
                move.sequence = seq
            moves._action_assign()
            picking.message_post_with_view('mail.message_origin_link',
                                           values={'self': picking, 'origin': order},
                                           subtype_id=self.env.ref('mail.mt_note').id)
        return True

    
    def ship(self, vals):
        """
        调用此方法，并传入对应包含发货行&数量的dict，创建对应送货单（库存单）/欠单
        若是第一次发货，建立库存单，后续补充发货都为欠单
        :param dict vals: {line_id: count}
        :return:
        """
        self.ensure_one()
        self._ship_create_picking(vals)
        return True

    
    def button_done(self):
        self.ensure_one()
        for line in self.order_line:
            if line.product_qty != line.qty_received:
                raise exceptions.ValidationError('未发货完毕不能锁定该采购单！')
        res = super(PurchaseOrder, self).button_done()
#         if self.slug and self._is_use_platform():
#             PurchaseOrderDao(self.env).update(self.slug, {'state': 'done'})
        return res

    
#     def action_view_picking(self):
#         '''
#         This function returns an action that display existing picking orders of given purchase order ids.
#         When only one found, show the picking immediately.
#         '''
#         action = self.env.ref('stock.action_picking_tree_all')
#         result = action.read()[0]

#         # override the context to get rid of the default filtering on operation type
#         result['context'] = {}
#         pick_ids = self.mapped('picking_ids')
#         # choose the view_mode accordingly
#         if not pick_ids or len(pick_ids) > 1:
#             result['domain'] = "[('id','in',%s), ('state', '!=', 'cancel')]" % (pick_ids.ids)
#         elif len(pick_ids) == 1:
#             res = self.env.ref('stock.view_picking_form', False)
#             result['views'] = [(res and res.id or False, 'form')]
#             result['res_id'] = pick_ids.id
#         return result

    
    def action_push_2_platform(self):
        """
        推送采购单数据到公共平台
        :return:
        """
        self.ensure_one()
        if self._is_use_platform():
            data = {
                'id': self.id,
                'no': self.name,
                'state': 'pending',
                'order_time': self.date_order,
                'company': self.company_id.name,
                'total': self.amount_total,
                'currency_symbol': self.currency_id.symbol,
                'currency_name': self.currency_id.name,
                'scenter_slug': self.partner_id.scenter_slug
            }
            r = PurchaseOrderDao(self.env).create(data)
            slug = r.get('slug', None)
            if slug:
                return self.write({'slug': slug})
            else:
                raise exceptions.ValidationError('采购订单推送失败')
        return True

    
    def action_accept(self):
        self.ensure_one()
        self.write({'state': 'purchase'})
#         if self.slug and self._is_use_platform():
#             PurchaseOrderDao(self.env).update(self.slug, {'state': 'purchase'})
        return True

    
    def action_refuse(self):
        for order in self:
            order.ensure_one()
            order.write({'state': 'cancel'})
            # if order.slug and order._is_use_platform():
            #     PurchaseOrderDao(order.env).update(order.slug, {'state': 'cancel'})
        return True

    # -*- 审批流相关逻辑 -*-
    @api.model
    def use_approval_config(self):
        """
        获取是否启用审批流的配置
        :return:
        """
        ICPSudo = self.env['ir.config_parameter'].sudo()
        return ICPSudo.get_param('srm_purchase.use_approval_workflow', default=False)

    @api.depends('state')
    
    def _compute_submit_btn_show(self):
        self.ensure_one()
        if any([self.state not in ['draft', 'sent'], not self.use_approval_config()]):
            self.submit_btn_show = False
        else:
            self.submit_btn_show = True

    #@api.depends('state', 'approval_workflow_id')
    
    def _compute_approval_btn_show(self):
        self.ensure_one()
        if any([self.state != 'to approve', not self.use_approval_config(), self.done, not self.approval_workflow_id]):
            self.approval_button_show = False
        else:
            if self.node_id.check_approval_access():
                self.approval_button_show = True
            else:
                self.approval_button_show = False

    #@api.depends('approval_workflow_id')
    
    def _compute_approval_log_show(self):
        self.ensure_one()
        if not (self.use_approval_config() and self.approval_workflow_id):
            self.approval_log_show = False
        else:
            self.approval_log_show = True

    @api.model
    def _get_approval_strategy(self):
        """
        重写覆盖原有的审批策略获取逻辑
        :return:
        """
        return self.env.ref('srm_purchase.default_purchase_approval_workflow')

    
    def approval_finish(self, is_pass, remark=''):
        self.ensure_one()
        if is_pass:
            self.button_approve()
        # else:
        #     self.button_cancel()

    
    def button_confirm(self):
        super(PurchaseOrder, self).button_confirm()
        context = {
            'active_model': self._name,
            'active_ids': self.ids,
            'active_id': self.id,
        }
        ICPSudo = self.env['ir.config_parameter'].sudo()
        use_approval_workflow_module = ICPSudo.get_param('srm_purchase.use_approval_workflow_module', default='')
        for record in self:
            if record.state in ['to approve'] and use_approval_workflow_module == 'True':
                record.get_approval_strategy().with_context(**context).action_create_approval_workflow()
        return True

    
    def button_approve(self, force=False):
        context = {
            'active_model': self._name,
            'active_ids': self.ids,
            'active_id': self.id,
        }
        ICPSudo = self.env['ir.config_parameter'].sudo()
        use_approval_workflow_module = ICPSudo.get_param('srm_purchase.use_approval_workflow_module', default='')
        for record in self:
            if record.state in ['to approve'] and self._context.get('is_server_action', False) is False:
                if use_approval_workflow_module == 'True':
                    return record.with_context(**context).return_approval_window()
        return super(PurchaseOrder, self).button_approve(force=force)

    def get_approval_strategy(self):
        module_name = 'approval'
        if not self.env.get('ir.module.module').sudo().search([('name', '=', module_name), ('state', '=', 'installed')]):
            raise exceptions.ValidationError('请先安装审批流模块！')
        model_id = self.env['ir.model'].search([('model', '=', self._name)]).id
        approval_strategy_objs = self.env.get('approval.strategy').sudo().search([('model_id', '=', model_id), ('enable', '=', True)])
        if len(approval_strategy_objs) < 1:
            if not self.env.get('approval.strategy').sudo().search([('model_id', '=', model_id)]):
                raise exceptions.ValidationError('请先创建审批策略！')
            else:
                raise exceptions.ValidationError('请先启动审批策略！')
        elif len(approval_strategy_objs) > 1:
            # 如果一个单据存在多个审批策略，先暂时去第一个审批策略。
            approval_strategy_objs = approval_strategy_objs[0]
        return approval_strategy_objs

    def return_approval_window(self):
        return self.get_approval_strategy().action_approval_window()


