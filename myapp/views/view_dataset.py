import datetime
import re
import shutil

from flask_appbuilder import action
from myapp.views.baseSQLA import MyappSQLAInterface as SQLAInterface
from wtforms.validators import DataRequired, Regexp  #WTForms是一个用于Python的Web表单生成和处理库，允许开发者轻松地创建和验证表单数据。
from myapp import app, appbuilder
from wtforms import StringField, SelectField
from flask_appbuilder.fieldwidgets import BS3TextFieldWidget, Select2Widget, Select2ManyWidget
from myapp.forms import MyBS3TextAreaFieldWidget, MySelect2Widget, MyCommaSeparatedListField, MySelect2ManyWidget, \
    MySelectMultipleField
from flask import jsonify, Markup, make_response
from .baseApi import MyappModelRestApi
from flask import g, request, redirect
import json, os, sys
from werkzeug.utils import secure_filename
import pysnooper
from sqlalchemy import or_
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
import importlib
from .base import (
    DeleteMixin,
    MyappFilter,
    MyappModelView,
)
from myapp import app, appbuilder, db
from flask_appbuilder import expose
from myapp.views.view_team import Project_Join_Filter, filter_join_org_project
from myapp.models.model_dataset import Dataset

conf = app.config


class Dataset_Filter(MyappFilter):
    """
    Dataset_Filter 是一个自定义的过滤器类，用于在数据集查询时实现权限过滤功能。具体来说，它实现了 apply 方法，根据当前用户的角色对数据集进行过滤。

    在 apply 方法中，首先获取当前用户的角色，然后判断如果用户是管理员（admin）则返回原始查询结果，否则只返回当前用户有权限查看的数据集。具体的权限判断逻辑是，只有数据集的所有者（owner 字段中包含当前用户名）或者数据集的 owner 字段包含通配符 * 时，用户才有权限查看该数据集。

    这样设计的目的是实现对数据集的访问权限控制，确保只有数据集的所有者或者有特定权限的用户才能查看对应的数据集信息
    """
    # @pysnooper.snoop()
    def apply(self, query, func):
        user_roles = [role.name.lower() for role in list(self.get_user_roles())]
        if "admin" in user_roles:
            return query  #如果是admin，则直接返回query信息

        return query.filter(
            or_( #or_ 函数用于在SQL查询中创建一个逻辑“或”（OR）条件
                self.model.owner.contains(g.user.username),  #来自Basefilter
                self.model.owner.contains('*')
            )
        ) #如果数据集的所有者是当前用户，或者数据集的所有者字段包含 *（表示公开），则用户有权查看该数据集。

"""
基于 Flask-AppBuilder 用于管理数据集视图，管理数据集（Dataset）的增删改查和相关操作。
这个类包含了许多属性和方法，用于配置数据集的展示、编辑、过滤、权限控制等功能。
"""
class Dataset_ModelView_base():  
    label_title = _('数据集')
    datamodel = SQLAInterface(Dataset) #用于指定数据集的数据模型，这里使用了 SQLAlchemy 的数据模型 SQLAInterface，并传入了 Dataset 表格
    base_permissions = ['can_add', 'can_show', 'can_edit', 'can_list', 'can_delete'] #用户对此视图权限，基本的权限列表，包括添加、展示、编辑、列表和删除等权限。

    base_order = ("id", "desc") #设置默认的数据集排序方式，这里按照数据集的 ID 降序排列
    order_columns = ['id'] #设置可以排序的列，默认为数据集的 ID 列
    base_filters = [["id", Dataset_Filter, lambda: []]]  # 设置权限过滤器，用了自定义的 Dataset_Filter 过滤器类。

    #用于设置在添加数据集时需要填写的字段
    add_columns = ['name', 'version', 'label', 'describe', 'source_type', 'source', 'field',
                   'usage', 'storage_class', 'file_type', 'url', 'download_url', 'path',
                   'storage_size', 'entries_num', 'duration', 'price', 'status', 'icon', 'owner', 'features']
    
    #用于设置在展示数据集时需要填写的字段
    show_columns = ['id', 'name', 'version', 'label', 'describe', 'segment', 'source_type', 'source',
                    'industry', 'field', 'usage', 'storage_class', 'file_type', 'status', 'url',
                    'path', 'download_url', 'storage_size', 'entries_num', 'duration', 'price', 'status', 'icon',
                    'owner', 'features']
    #用于设置可以搜索的字段
    search_columns = ['name', 'version', 'label', 'describe', 'source_type', 'source', 'field', 'usage','storage_class', 'file_type', 'status', 'url', 'path', 'download_url']
    #用于设置特定标签的列名
    spec_label_columns = {
        "subdataset": _("子数据集名称"),
        "source_type": _("来源类型"),
        "source": _("数据来源"),
        "usage": _("数据用途"),
        "research": _("研究方向"),
        "storage_class": _("存储类型"),
        "years": _("数据年份"),
        "url": _("相关网址"),
        "url_html": _("相关网址"),
        "path": _("本地路径"),
        "path_html": _("本地路径"),
        "entries_num": _("条目数量"),
        "duration": _("文件时长"),
        "price": _("价格"),
        "icon": _("示例图"),
        "icon_html": _("示例图"),
        "ops_html": _("操作"),
        "features": _("特征列"),
        "segment": _("分区")
    }

    edit_columns = add_columns #用于设置在编辑数据集时可以修改的字段，这里与 add_columns 相同。

    #设置了一个属性 list_columns，用于设置在数据集列表中显示的字段
    list_columns = ['icon_html', 'name', 'version', 'label', 'describe','owner', 'source_type', 'source', 'status',
                    'field', 'url_html', 'download_url_html', 'usage', 'storage_class', 'file_type', 'path_html', 'storage_size', 'entries_num', 'price']
    #用于设置列表中各列的宽度
    cols_width = {
        "name": {"type": "ellip1", "width": 200},
        "label": {"type": "ellip2", "width": 200},
        "version": {"type": "ellip2", "width": 100},
        "describe": {"type": "ellip2", "width": 300},
        "field": {"type": "ellip1", "width": 100},
        "source_type": {"type": "ellip1", "width": 100},
        "source": {"type": "ellip1", "width": 100},
        "industry": {"type": "ellip1", "width": 100},
        "url_html": {"type": "ellip1", "width": 200},
        "download_url_html": {"type": "ellip1", "width": 200},
        "path_html": {"type": "ellip1", "width": 200},
        "storage_class": {"type": "ellip1", "width": 100},
        "storage_size": {"type": "ellip1", "width": 100},
        "file_type": {"type": "ellip1", "width": 100},
        "owner": {"type": "ellip1", "width": 200},
        "status": {"type": "ellip1", "width": 100},
        "entries_num": {"type": "ellip1", "width": 200},
        "duration": {"type": "ellip1", "width": 100},
        "price": {"type": "ellip1", "width": 100},
        "years": {"type": "ellip2", "width": 100},
        "usage": {"type": "ellip1", "width": 200},
        "research": {"type": "ellip2", "width": 100},
        "icon_html": {"type": "ellip1", "width": 100},
        "ops_html": {"type": "ellip1", "width": 200},
    }

    #用于展示数据集中的列信息示例，新增数据集时最下方的详情弹窗
    features_demo = '''
{
  "column1": {
    # feature type
    "type": "dict,list,tuple,Value,Sequence,Array2D,Array3D,Array4D,Array5D,Translation,TranslationVariableLanguages,Audio,Image,Video,ClassLabel",

    # data type in dict,list,tuple,Value,Sequence,Array2D,Array3D,Array4D,Array5D
    "dtype": "null,bool,int8,int16,int32,int64,uint8,uint16,uint32,uint64,float16,float32,float64,time32[(s|ms)],time64[(us|ns)],timestamp[(s|ms|us|ns)],timestamp[(s|ms|us|ns),tz=(tzstring)],date32,date64,duration[(s|ms|us|ns)],decimal128(precision,scale),decimal256(precision,scale),binary,large_binary,string,large_string"

    # length of Sequence
    "length": 10

    # dimension of Array2D,Array3D,Array4D,Array5D
    "shape": (1, 2, 3, 4, 5),

    # sampling rate of Audio
    "sampling_rate":16000,
    "mono": true,
    "decode": true

    # decode of Image
    "decode": true

    # class of ClassLabel
    "num_classes":3,
    "names":['class1','class2','class3'] 

  },
}
    '''
    #用于设置在添加数据集时额外需要填写的字段及其验证器等信息。
    add_form_extra_fields = {
        "name": StringField( #StringField 通常用于表单中的文本输入，如用户名、邮箱、密码等。它可以接受多种字符类型的输入，并根据配置的验证器进行验证
            label= _('名称'),  #这里使用了一个翻译函数 _('名称')，它可能是用于国际化，将英文标签翻译成中文。
            description= _('数据集英文名，小写'),
            default='',
            widget=BS3TextFieldWidget(), #字段的HTML小部件，用于在表单中渲染该字段。这里使用了 BS3TextFieldWidget()，它可能是Bootstrap 3的文本字段小部件。
            validators=[DataRequired(), Regexp("^[a-z][a-z0-9_]*[a-z0-9]$"), ] #字段的验证器列表。这里使用了两个验证器，必填信息
        ),
        "version": StringField(
            label= _('版本'),
            description= _('数据集版本'),
            default='latest',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired(), Regexp("^[a-z][a-z0-9_\-]*[a-z0-9]$"), ]
        ),
        "subdataset": StringField(
            label= _('子数据集'),
            description= _('子数据集名称，不存在子数据集，与name同值'),
            default='',
            widget=BS3TextFieldWidget(),
            validators=[]
        ),
        "label": StringField(
            label= _('标签'),
            default='',
            description='',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "describe": StringField(
            label= _('描述'),
            default='',
            description= _('数据集描述'),
            widget=MyBS3TextAreaFieldWidget(),
            validators=[DataRequired()]
        ),
        "industry": SelectField(
            label= _('行业'),
            description= _('行业分类'),
            widget=MySelect2Widget(can_input=True),
            default='',
            choices=[[_(x), _(x)] for x in
                     ['农业', '生物学', '气候+天气', '复杂网络', '计算机网络', '网络安全', '数据挑战', '地球科学', '经济学', '教育', '能源', '娱乐', '金融',
                      'GIS', '政府', '医疗', '图像处理', '机器学习', '博物馆', '自然语言', '神经科学', '物理', '前列腺癌', '心理学+认知', '公共领域', '搜索引擎',
                      '社交网络', '社会科学', '软件', '运动', '时间序列', '交通', '电子竞技']],
            validators=[]
        ),
        "field": SelectField(
            label= _('领域'),
            description='',
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ['视觉', "语音", "自然语言",'多模态', "风控", "搜索", '推荐','广告']],
            validators=[]
        ),
        "source_type": SelectField(
            label= _('数据源类型'),
            description='',
            widget=Select2Widget(),
            default= _('开源'),
            choices=[[_(x), _(x)] for x in ["开源", "自产", "购买"]],
            validators=[]
        ),
        "source": SelectField(
            label= _('数据来源'),
            description= _('数据来源，可自己填写'),
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in
                     ['github', "kaggle", "ali", 'uci', 'aws', 'google', "company1", "label-team1", "web1"]],
            validators=[]
        ),
        "file_type": MySelectMultipleField(
            label= _('文件类型'),
            description='',
            widget=Select2ManyWidget(),
            choices=[[x, x] for x in ["png", "jpg", 'txt', 'csv', 'wav', 'mp3', 'mp4', 'nv4', 'zip', 'gz']],
        ),
        "storage_class": SelectField(
            label= _('存储类型'),
            description='',
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ["压缩", "未压缩"]],
        ),
        "storage_size": StringField(
            label= _('存储大小'),
            description='',
            widget=BS3TextFieldWidget(),
        ),
        "owner": StringField(
            label= _('责任人'),
            default='*',
            description= _('责任人,逗号分隔的多个用户,*表示公开'),
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "status": SelectField(
            label= _('状态'),
            description= _('数据集状态'), 
            widget=MySelect2Widget(can_input=True),
            choices=[[_(x), _(x)] for x in ["损坏", "正常", '未购买', '已购买', '未标注', '已标注', '未校验', '已校验']],
        ),
        "url": StringField(
            label= _('相关网址'),
            description='',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "path": StringField(
            label= _('本地路径'),
            description='',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "download_url": StringField(
            label= _('下载地址'),
            description='',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            default=''
        ),
        "features": StringField(
            label= _('特征列'),
            description= _('数据集中的列信息'),
            widget=MyBS3TextAreaFieldWidget(rows=3, tips=Markup('<pre><code>' + features_demo + "</code></pre>")),
            default=''
        )
    }

    #用于设置在编辑数据集时额外需要填写的字段，这里与 add_form_extra_fields 相同。
    edit_form_extra_fields = add_form_extra_fields

    #用于指示是否支持导入和下载数据
    import_data = True
    download_data = True

    '''
    用于在添加数据集之前执行的操作。如果数据集的所有者（owner）为空，则将其设置为当前用户的用户名加上通配符 *；
    如果数据集的图标（icon）为空，则设置默认图标路径；如果数据集的版本（version）为空，则将其设置为 'latest'；
    如果数据集的子数据集名称（subdataset）为空，则将其设置为数据集的名称。
    '''
    def pre_add(self, item):
        if not item.owner:
            item.owner = g.user.username + ",*"
        if not item.icon:
            item.icon = '/static/assets/images/dataset.png'
        if not item.version:
            item.version = 'latest'
        if not item.subdataset:
            item.subdataset = item.name

    def pre_update(self, item):
        self.pre_add(item)  #用于在更新数据集之前执行的操作，实际上调用了 pre_add 方法。

    '''   
    用于检查用户是否有编辑数据集的权限。如果用户不是管理员，并且不是数据集的创建者或者不在数据集的所有者列表中，
    则返回 False，表示没有权限；否则返回 True。同时也定义了一个方法 check_delete_permission，
    其实现与 check_edit_permission 相同。
    '''
    def check_edit_permission(self, item):
        if not g.user.is_admin() and g.user.username != item.created_by.username and g.user.username not in item.owner:
            return False
        return True
    check_delete_permission = check_edit_permission

    # 将外部存储保存到本地存储中心
    @action("save_store", "备份", "备份数据到当前集群?", "fa-trash", single=True, multiple=False)
    # @pysnooper.snoop()
    def save_store(self, dataset):   #用于备份数据集到当前集群。当点击该操作时，会调用 update_dataset 异步任务，并传入数据集的 ID。
        from myapp.tasks.async_task import update_dataset
        kwargs = {
            "dataset_id": dataset.id,
        }
        update_dataset.apply_async(kwargs=kwargs)
        # update_dataset(task=None,dataset_id=item.id)

    @expose("/upload/<dataset_id>", methods=["POST"])
    # @pysnooper.snoop()
    def upload_dataset(self, dataset_id): #用于处理上传数据集的请求。具体的实现逻辑包括接收文件数据、将文件保存到本地路径等操作。
        dataset = db.session.query(Dataset).filter_by(id=int(dataset_id)).first()
        filename = request.form['filename']
        partition = request.form.get('partition', '')

        print(request.form)
        print(request.files)
        file = request.files['file']
        file_data = file.stream.read()
        data_dir = f'/data/k8s/kubeflow/dataset/{dataset.name}/{dataset.version}'
        os.makedirs(data_dir, exist_ok=True)
        save_path = os.path.join(data_dir, secure_filename(filename))
        current_chunk = int(request.form['current_chunk'])

        if os.path.exists(save_path) and current_chunk == 0:
            os.remove(save_path)
        try:
            with open(save_path, 'ab') as f:
                f.seek(int(request.form['current_offset']))
                f.write(file_data)
        except OSError:
            # log.exception will include the traceback so we can see what's wrong
            print('Could not write to file')
            return make_response(("Not sure why,"" but we couldn't write the file to disk", 500))

        total_chunks = int(request.form['total_chunk'])

        if current_chunk + 1 == total_chunks:
            # This was the last chunk, the file should be complete and the size we expect
            if os.path.getsize(save_path) != int(request.form['total_size']):
                print(f"File {filename} was completed, but has a size mismatch.Was {os.path.getsize(save_path)} but we expected {request.form['total_size']} ")
                return make_response(('Size mismatch', 500))
            else:
                print(f'File {filename} has been uploaded successfully')
                # save_type = request.form['save_type']  # 替换，还是追加数据集
                dataset.path = (dataset.path or '') + "\n" + save_path
                dataset.path = '\n'.join(list(set([x.strip() for x in dataset.path.split('\n') if x.strip()])))
                if partition:
                    segment = json.loads(dataset.segment) if dataset.segment else {}
                    if partition not in segment:
                        segment[partition] = [save_path]
                    else:
                        segment[partition].append(save_path)
                        segment[partition] = list(set(segment[partition]))
                    dataset.segment = json.dumps(segment, indent=4, ensure_ascii=False)
                db.session.commit()
        else:
            print(f'Chunk {current_chunk + 1} of {total_chunks} for file {filename} complete')

        return make_response(("Chunk upload successful", 200))

    # # 将外部存储保存到本地存储中心
    # @expose("/download/<dataset_name>", methods=["GET","POST"])
    # @expose("/download/<dataset_name>/<dataset_version>", methods=["GET",'POST'])
    # def download(self, dataset_name,dataset_version=None):
    #     try:
    #         store_type = conf.get('STORE_TYPE', 'minio')
    #         params = importlib.import_module(f'myapp.utils.store.{store_type}')
    #         store_client = getattr(params, store_type.upper() + '_client')(**conf.get('STORE_CONFIG', {}))
    #         remote_file_path = f'/dataset/{dataset_name}/{dataset_version if dataset_version else "latest"}'
    #         urls = store_client.get_download_url(remote_file_path)
    #
    #         return jsonify({
    #             "status":0,
    #             "result":{
    #                 "store_type": conf.get('STORE_TYPE', 'minio'),
    #                 "download_urls":urls
    #             },
    #             "message":"success"
    #         })
    #     except Exception as e:
    #         print(e)
    #         return jsonify({
    #             "status": 1,
    #             "result": '',
    #             "message": str(e)
    #         })

    # 将外部存储保存到本地存储中心
    @expose("/download/<dataset_id>", methods=["GET", "POST"])
    @expose("/download/<dataset_id>/<partition>", methods=["GET", "POST"])
    def download_dataset(self, dataset_id, partition=''):  #用于处理下载数据集的请求。根据数据集的 ID 和分区信息，生成下载链接并返回给用户。
        # 生成下载链接
        def path2url(path):
            if 'http://' in path or "https://" in path: #检查路径是否已经是URL，如果是，直接返回
                return path
            if re.match('^/mnt/', path):
                return f'{request.host_url.strip("/")}/static{path}'  #路径以/mnt/开头，将其转换为可通过Web访问的URL
            if re.match('^/data/k8s/kubeflow/dataset', path):
                return f'{request.host_url.strip("/")}/static{path.replace("/data/k8s/kubeflow", "")}'
                #路径以/data/k8s/kubeflow/dataset开头，也转换为URL，同时去除这部分路径。
            
        dataset = db.session.query(Dataset).filter_by(id=int(dataset_id)).first()
        try:
            download_url = []
            if dataset.path:  #path为本地持久化路径
                # 如果存储在集群数据集中心
                # 如果存储在个人目录
                paths = dataset.path.split('\n')
                for path in paths:
                    download_url.append(path2url(path))

            # 如果存储在外部链接
            elif dataset.download_url:
                download_url = dataset.download_url.split('\n')
            else:
                # 如果存储在对象存储中
                store_type = conf.get('STORE_TYPE', 'minio')
                params = importlib.import_module(f'myapp.utils.store.{store_type}')
                store_client = getattr(params, store_type.upper() + '_client')(**conf.get('STORE_CONFIG', {}))
                remote_file_path = f'/dataset/{dataset.name}/{dataset.version}'
                download_url = store_client.get_download_url(remote_file_path)

            if partition:
                segment = json.loads(dataset.segment) if dataset.segment else {}
                if partition in segment:
                    download_url = segment[partition]
                    download_url = [path2url(url) for url in download_url]

            return jsonify({
                "status": 0,
                "result": {
                    "store_type": conf.get('STORE_TYPE', 'minio'),
                    "download_urls": download_url
                },
                "message": "success"
            })
        except Exception as e:
            print(e)
            return jsonify({
                "status": 1,
                "result": '',
                "message": str(e)
            })


    '''
    用于预览数据集的内容。这里的实现逻辑包括接收请求参数、返回数据集预览信息等操作。
    '''
    @expose("/preview/<dataset_name>", methods=["GET", "POST"])
    @expose("/preview/<dataset_name>/<dataset_version>", methods=["GET", 'POST'])
    @expose("/preview/<dataset_name>/<dataset_version>/<dataset_segment>", methods=["GET", 'POST'])
    def preview(self):
        _args = request.get_json(silent=True) or {}
        _args.update(request.args)
        _args.update(json.loads(request.args.get('form_data', {})))
        info = {}
        info.update(
            {
                "rows": [
                    {
                        "row_idx": 0,
                        "row": {
                            "col1": "",
                            "col2": "",
                            "col3": "",
                            "label1": [""],
                            "no_answer": False
                        },
                        "truncated_cells": []
                    }
                ]
            }
        )
        return jsonify(info)


class Dataset_ModelView_Api(Dataset_ModelView_base, MyappModelRestApi):
    datamodel = SQLAInterface(Dataset)  #与后端数据库连接，datamodel 被设置为 SQLAInterface(Dataset)，表示该类操作的数据模型是 Dataset
    route_base = '/dataset_modelview/api' #表示该类的路由基础路径为 /dataset_modelview/api

# 将这个类注册到 Flask-AppBuilder 中，使其能够处理相关的 API 请求。
# 这个类主要用于定义数据集的 RESTful API 接口，包括对数据集的增删改查等操作。
appbuilder.add_api(Dataset_ModelView_Api) 

