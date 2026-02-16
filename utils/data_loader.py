import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import xml.etree.ElementTree as ET
import streamlit as st
from pypdf import PdfReader


class DocumentLoader:
    """医薬品文書を読み込むクラス"""

    def __init__(self, data_dir: str = "data") -> None:
        """
        Args:
            data_dir: データフォルダのパス
        """
        self.data_dir = Path(data_dir)

    def _detect_document_type(self, file_name: str) -> str:
        """
        ファイル名から文書タイプを判定

        Args:
            file_name: ファイル名

        Returns:
            文書タイプ
        """
        # 全角を半角に変換
        file_name_normalized = unicodedata.normalize('NFKC', file_name)

        # 判定ロジック（優先順位順）- 正規化後のファイル名で判定
        if file_name_normalized.endswith('.xml'):
            return '電子添文'
        elif '_IF.pdf' in file_name_normalized or 'IF.pdf' in file_name_normalized:
            return 'インタビューフォーム'
        elif '_RMP' in file_name_normalized or 'RMP' in file_name_normalized:
            return '医薬品リスク管理計画'
        elif '患者向けガイド' in file_name_normalized or '患者向けガイド' in file_name:
            return '患者向け医薬品ガイド'
        else:
            return 'その他'
    
    def _clean_text(self, text: str) -> str:
        """
        テキストを正規化
        
        Args:
            text: 元のテキスト
            
        Returns:
            正規化されたテキスト
        """
        # 改行の整理
        text = re.sub(r'\n{3,}', '\n\n', text)  # 3つ以上の連続改行を2つに
        
        # 全角・半角の統一
        text = text.replace('　', ' ')  # 全角スペースを半角に
        
        # 不要な空白の除去
        text = re.sub(r' {2,}', ' ', text)  # 連続スペースを1つに
        
        return text.strip()
    
    def _extract_sections_from_text(self, text: str, file_name: str) -> List[Dict[str, Any]]:
        """
        テキストから見出し単位でセクションを抽出
        
        Args:
            text: 全文テキスト
            file_name: ファイル名
            
        Returns:
            セクションのリスト
        """
        sections = []
        
        # ページ区切りで分割
        pages = text.split('--- ページ')
        
        for page_text in pages:
            if not page_text.strip():
                continue
            
            # ページ番号の抽出
            page_match = re.match(r'(\d+) ---', page_text)
            page_num = int(page_match.group(1)) if page_match else None
            
            section_text = page_text
            if page_match:
                section_text = page_text[page_match.end():]
            
            # セクションとして保存
            sections.append({
                'text': self._clean_text(section_text),
                'page': page_num,
                'heading': self._extract_first_heading(section_text),
                'file_name': file_name
            })
        
        return sections
    
    def _extract_first_heading(self, text: str) -> Optional[str]:
        """テキストから最初の見出しを抽出"""
        lines = text.split('\n')[:5]  # 最初の5行を確認
        
        for line in lines:
            line = line.strip()
            # 数字や記号で始まる見出しらしい行
            if re.match(r'^[\d\【].{3,50}', line):
                return line
        
        return None

    def load_pdf(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        PDFファイルを読み込んでテキストとメタデータを返す

        Args:
            file_path: PDFファイルのパス

        Returns:
            dict: 文書情報
        """
        try:
            reader = PdfReader(file_path)

            full_text_parts: List[str] = []
            for page_num, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                full_text_parts.append(f"\n--- ページ {page_num} ---\n{page_text}")
            full_text = "".join(full_text_parts)
            
            # 文書タイプの判定
            doc_type = self._detect_document_type(file_path.name)
            
            # セクション分割
            sections = self._extract_sections_from_text(full_text, file_path.name)
            
            return {
                'full_text': full_text,
                'sections': sections,
                'file_name': file_path.name,
                'file_path': str(file_path),
                'pages': len(reader.pages),
                'doc_type': doc_type,
                'doc_type_ja': doc_type
            }
            
        except Exception as e:
            print(f"❌ PDFの読み込みに失敗: {file_path.name}")
            print(f"   エラー: {str(e)}")
            return None

    def load_xml(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        XMLファイル(電子添文)を読み込む
        
        Args:
            file_path: XMLファイルのパス
            
        Returns:
            dict: 文書情報
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # XMLをテキストに変換（簡易版）
            text = ET.tostring(root, encoding='unicode', method='text')
            
            sections = [{
                'text': self._clean_text(text),
                'page': None,
                'heading': '電子添文',
                'file_name': file_path.name
            }]
            
            return {
                'full_text': text,
                'sections': sections,
                'file_name': file_path.name,
                'file_path': str(file_path),
                'pages': None,
                'doc_type': '電子添文',
                'doc_type_ja': '電子添文'
            }
            
        except Exception as e:
            print(f"❌ XMLの読み込みに失敗: {file_path.name}")
            print(f"   エラー: {str(e)}")
            return None

    def load_product_documents(self, product_type: str, company_type: str) -> List[Dict[str, Any]]:
        """
        指定された製品タイプと会社タイプの文書を読み込む
        
        Args:
            product_type: "血漿分画製剤", "IBD製剤", "抗うつ製剤" など
            company_type: "自社" or "他社"
            
        Returns:
            List[Dict]: 読み込んだ文書のリスト
        """
        documents = []
        
        # データフォルダのパス
        folder_path = self.data_dir / product_type / company_type
        
        if not folder_path.exists():
            print(f"⚠️ フォルダが存在しません: {folder_path}")
            return documents
        
        # PDFとXMLファイルを再帰的に探索
        pdf_files = list(folder_path.rglob("*.pdf"))
        xml_files = list(folder_path.rglob("*.xml"))
        
        all_files = pdf_files + xml_files
        
        print(f"  📂 {len(all_files)}個のファイルを発見 (PDF: {len(pdf_files)}, XML: {len(xml_files)})")
        
        # 各ファイルを読み込み
        for file_path in all_files:
            if file_path.suffix == '.pdf':
                doc = self.load_pdf(file_path)
            elif file_path.suffix == '.xml':
                doc = self.load_xml(file_path)
            else:
                continue
            
            if doc:
                # メタデータを追加
                doc['product_type'] = product_type
                doc['company_type'] = company_type
                
                # 製品名を推定（フォルダ名から）
                product_name = file_path.parent.name
                doc['product_name'] = product_name
                
                documents.append(doc)
        
        return documents
    
    def load_all_documents(self) -> List[Dict[str, Any]]:
        """
        全製品タイプ、全会社タイプの文書を読み込む
        
        Returns:
            List[Dict]: 読み込んだ全文書のリスト
        """
        all_documents = []
        
        # 製品タイプの定義
        product_types = ["血漿分画製剤", "IBD製剤", "抗うつ製剤"]
        company_types = ["自社", "他社"]
        
        print("\n=== 全製品の文書を読み込み ===")
        
        for product_type in product_types:
            product_path = self.data_dir / product_type
            if not product_path.exists():
                print(f"⚠️ {product_type}フォルダが存在しません")
                continue
            
            print(f"\n【{product_type}】")
            
            for company_type in company_types:
                print(f"  {company_type}:")
                docs = self.load_product_documents(product_type, company_type)
                all_documents.extend(docs)
                print(f"    → {len(docs)}文書読み込み完了")
        
        return all_documents
    
    def get_available_products(self) -> Dict[str, Dict[str, List[str]]]:
        """
        利用可能な全製品リストを取得
        
        Returns:
            Dict: {
                '血漿分画製剤': {'自社': [...], '他社': [...]},
                'IBD製剤': {'自社': [...], '他社': [...]},
                '抗うつ製剤': {'自社': [...], '他社': [...]}
            }
        """
        products: Dict[str, Dict[str, List[str]]] = {}
        
        # 製品タイプの定義
        product_types = ["血漿分画製剤", "IBD製剤", "抗うつ製剤"]
        
        for product_type in product_types:
            product_path = self.data_dir / product_type
            if not product_path.exists():
                continue
            
            products[product_type] = {'自社': [], '他社': []}
            
            for company_type in ('自社', '他社'):
                company_path = product_path / company_type
                if company_path.exists():
                    products[product_type][company_type] = sorted(
                        d.name for d in company_path.iterdir() if d.is_dir()
                    )
        
        return products
    
    def get_document_stats(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        読み込んだ文書の統計情報を取得する。

        Args:
            documents: 文書辞書のリスト

        Returns:
            total_docs, by_type, by_product, by_product_type, by_company を含む辞書
        """
        stats = {
            'total_docs': len(documents),
            'by_type': {},
            'by_product': {},
            'by_product_type': {},
            'by_company': {}
        }
        
        for doc in documents:
            # 文書タイプ別
            doc_type = doc.get('doc_type_ja', '不明')
            stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
            
            # 製品別
            product = doc.get('product_name', '不明')
            stats['by_product'][product] = stats['by_product'].get(product, 0) + 1
            
            # 製品タイプ別
            product_type = doc.get('product_type', '不明')
            stats['by_product_type'][product_type] = stats['by_product_type'].get(product_type, 0) + 1
            
            # 会社タイプ別
            company_type = doc.get('company_type', '不明')
            stats['by_company'][company_type] = stats['by_company'].get(company_type, 0) + 1
        
        return stats

    def load_drug_prices(self) -> Dict[str, Any]:
        """
        薬価情報を読み込む。

        Returns:
            {'注射剤': DataFrame, '内服薬': DataFrame, ...} の辞書
        """
        import pandas as pd

        prices: Dict[str, Any] = {}
        price_dir = self.data_dir / "薬価"

        if not price_dir.exists():
            print(f"⚠️ 薬価フォルダが存在しません: {price_dir}")
            return prices

        excel_files = list(price_dir.glob("*.xlsx"))
        print(f"\n=== 薬価ファイルを読み込み ===")
        print(f"発見したファイル数: {len(excel_files)}")

        for excel_file in excel_files:
            try:
                print(f"  読み込み中: {excel_file.name}")
                df = pd.read_excel(excel_file)

                if '注射剤' in excel_file.name:
                    prices['注射剤'] = df
                elif '内服薬' in excel_file.name or '内服' in excel_file.name:
                    prices['内服薬'] = df
                else:
                    prices[excel_file.stem] = df

                print(f"    → {len(df)}行 × {len(df.columns)}列")

            except Exception as e:
                print(f"❌ 薬価ファイルの読み込みに失敗: {excel_file.name}")
                print(f"   エラー: {str(e)}")

        return prices


def test_loader() -> None:
    """データローダーの動作確認用。"""
    loader = DocumentLoader()
    
    print("=" * 70)
    print("=== 利用可能な製品一覧 ===")
    products = loader.get_available_products()
    for product_type, companies in products.items():
        print(f"\n【{product_type}】")
        for company_type, product_list in companies.items():
            print(f"  {company_type}: {len(product_list)}製品")
    
    # 全文書を読み込み
    all_docs = loader.load_all_documents()
    
    print("\n" + "=" * 70)
    print(f"=== 読み込み完了 ===")
    print(f"総文書数: {len(all_docs)}")
    
    if all_docs:
        stats = loader.get_document_stats(all_docs)
        
        print(f"\n【製品タイプ別】")
        for product_type, count in stats['by_product_type'].items():
            print(f"  {product_type}: {count}文書")
        
        print(f"\n【会社タイプ別】")
        for company_type, count in stats['by_company'].items():
            print(f"  {company_type}: {count}文書")
        
        print(f"\n【文書タイプ別】")
        for doc_type, count in stats['by_type'].items():
            print(f"  {doc_type}: {count}文書")
        
        # IFファイルの統計
        if_docs = [d for d in all_docs if d['doc_type'] == 'インタビューフォーム']
        print(f"\n【インタビューフォーム】")
        print(f"  総数: {len(if_docs)}文書")
        if_by_product = {}
        for doc in if_docs:
            pt = doc['product_type']
            if_by_product[pt] = if_by_product.get(pt, 0) + 1
        for pt, count in if_by_product.items():
            print(f"  {pt}: {count}文書")
    
    # 薬価情報の読み込み
    print("\n" + "=" * 70)
    prices = loader.load_drug_prices()
    
    if prices:
        print(f"\n【薬価データ】")
        for category, df in prices.items():
            print(f"  {category}: {len(df)}行")
            if len(df) > 0:
                print(f"    列: {list(df.columns[:5])}...")


if __name__ == "__main__":
    test_loader()