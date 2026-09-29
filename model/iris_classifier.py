"""
Iris 붓꽃 품종 분류 머신러닝 파이프라인
- 데이터: Scikit-learn load_iris
- 모델: DecisionTreeClassifier (최대 깊이 3) 및 다중 모델 벤치마크
- 평가: Stratified K-Fold CV, Confusion Matrix, Classification Report
- 시각화: Decision Tree Diagram, Feature Importance, Decision Boundary
"""

import os
import sys

# 윈도우 콘솔 UTF-8 출력 보장
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from matplotlib.colors import ListedColormap

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style='whitegrid', font='Malgun Gothic')


class IrisClassifier:
    """아이리스 붓꽃 분류 머신러닝 파이프라인 클래스"""

    def __init__(self, max_depth: int = 3, random_state: int = 42):
        self.max_depth = max_depth
        self.random_state = random_state
        self.model = DecisionTreeClassifier(max_depth=self.max_depth, random_state=self.random_state)
        self.model_2d = None
        self.feature_cols = None
        self.target_names = None
        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None

    def load_and_split_data(self, test_size: float = 0.2):
        """데이터 로드 및 계층적 샘플링(Stratified Split) 분할"""
        iris = load_iris(as_frame=True)
        df = iris.frame.copy()
        self.feature_cols = iris.feature_names
        self.target_names = iris.target_names

        X = df[self.feature_cols]
        y = df['target']

        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.random_state, stratify=y
        )
        print(f"[데이터 분할 완료] Train={self.X_train.shape[0]}개, Test={self.X_test.shape[0]}개")
        return self

    def train(self):
        """의사결정나무 모델 학습"""
        if self.X_train is None:
            self.load_and_split_data()
        self.model.fit(self.X_train, self.y_train)
        print("[의사결정나무 모델 학습 완료]")
        return self

    def evaluate(self):
        """모델 성능 평가 (정확도, 오차행렬, 분류성적표)"""
        y_pred = self.model.predict(self.X_test)
        acc = accuracy_score(self.y_test, y_pred)
        print(f"\n[평가 결과] 테스트 세트 정확도: {acc * 100:.2f}% (30개 중 {int(acc * len(self.y_test))}개 정답)")
        print("\n" + "=" * 60)
        print("분류 성적표 (Classification Report):")
        print("=" * 60)
        print(classification_report(self.y_test, y_pred, target_names=self.target_names))
        return acc

    def benchmark_models(self):
        """5개 머신러닝 알고리즘 성능 비교 벤치마크"""
        models = {
            'Decision Tree': DecisionTreeClassifier(max_depth=3, random_state=self.random_state),
            'Logistic Regression': LogisticRegression(max_iter=200, random_state=self.random_state),
            'Random Forest': RandomForestClassifier(n_estimators=50, random_state=self.random_state),
            'K-Nearest Neighbors (K=3)': KNeighborsClassifier(n_neighbors=3),
            'Support Vector Machine': SVC(kernel='linear', random_state=self.random_state)
        }

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=self.random_state)
        records = []

        print("\n" + "=" * 65)
        print("다중 머신러닝 알고리즘 5-Fold 교차 검증 및 테스트 비교:")
        print("=" * 65)
        for name, clf in models.items():
            cv_scores = cross_val_score(clf, self.X_train, self.y_train, cv=cv, scoring='accuracy')
            clf.fit(self.X_train, self.y_train)
            test_acc = accuracy_score(self.y_test, clf.predict(self.X_test))
            records.append({
                '알고리즘': name,
                'CV 평균 정확도': f"{cv_scores.mean()*100:.2f}% (±{cv_scores.std()*100:.2f}%)",
                '테스트 정확도': f"{test_acc*100:.2f}%"
            })

        df_bench = pd.DataFrame(records).sort_values(by='테스트 정확도', ascending=False)
        print(df_bench.to_string(index=False))
        return df_bench

    def save_visualizations(self, output_dir: str = 'images'):
        """트리 구조, 특성 중요도, 오차 행렬, 2D 결정 경계면 시각화 이미지 저장"""
        os.makedirs(output_dir, exist_ok=True)
        y_pred = self.model.predict(self.X_test)
        acc = accuracy_score(self.y_test, y_pred)

        # 1. 트리 구조 시각화
        fig, ax = plt.subplots(figsize=(15, 8))
        plot_tree(
            self.model,
            feature_names=self.feature_cols,
            class_names=self.target_names,
            filled=True,
            rounded=True,
            fontsize=10,
            ax=ax
        )
        ax.set_title("의사결정나무(Decision Tree) 분류 규칙 다이어그램 (max_depth=3)", fontsize=14, pad=15, fontweight='bold')
        plt.tight_layout()
        tree_path = os.path.join(output_dir, 'iris_decision_tree_structure.png')
        plt.savefig(tree_path, dpi=150)
        plt.close()
        print(f"[시각화 저장] 트리 구조 다이어그램: {tree_path}")

        # 2. 특성 중요도 시각화
        feat_imp = pd.Series(self.model.feature_importances_, index=self.feature_cols).sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        sns.barplot(x=feat_imp.values, y=feat_imp.index, hue=feat_imp.index, palette='viridis', legend=False, ax=ax)
        ax.set_title("의사결정나무 모델의 특성 중요도 (Feature Importances)", fontsize=13, pad=15, fontweight='bold')
        ax.set_xlabel("중요도 (Gini Importance)", fontsize=11)
        ax.set_ylabel("")
        for i, v in enumerate(feat_imp.values):
            ax.text(v + 0.01, i, f"{v:.4f} ({v*100:.1f}%)", va='center', fontsize=10.5, fontweight='bold', color='#1a365d')
        ax.set_xlim(0, max(feat_imp.values) + 0.15)
        plt.tight_layout()
        imp_path = os.path.join(output_dir, 'iris_feature_importance.png')
        plt.savefig(imp_path, dpi=150)
        plt.close()
        print(f"[시각화 저장] 특성 중요도 차트: {imp_path}")

        # 3. 오차 행렬 히트맵
        cm = confusion_matrix(self.y_test, y_pred)
        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=self.target_names, yticklabels=self.target_names, cbar=False, ax=ax)
        ax.set_title(f"테스트 세트 오차 행렬 (Confusion Matrix)\n정확도: {acc*100:.1f}%", fontsize=13, pad=15, fontweight='bold')
        ax.set_xlabel("예측 품종 (Predicted Class)", fontsize=11)
        ax.set_ylabel("실제 품종 (Actual Class)", fontsize=11)
        plt.tight_layout()
        cm_path = os.path.join(output_dir, 'iris_confusion_matrix.png')
        plt.savefig(cm_path, dpi=150)
        plt.close()
        print(f"[시각화 저장] 오차 행렬 차트: {cm_path}")

        # 4. 2D 결정 경계면 시각화
        top2_cols = ['petal length (cm)', 'petal width (cm)']
        X_train_2d = self.X_train[top2_cols]
        X_test_2d = self.X_test[top2_cols]

        dt_2d = DecisionTreeClassifier(max_depth=self.max_depth, random_state=self.random_state)
        dt_2d.fit(X_train_2d, self.y_train)

        x_min, x_max = self.X_train[top2_cols[0]].min() - 0.5, self.X_train[top2_cols[0]].max() + 0.5
        y_min, y_max = self.X_train[top2_cols[1]].min() - 0.5, self.X_train[top2_cols[1]].max() + 0.5
        xx, yy = np.meshgrid(np.arange(x_min, x_max, 0.02), np.arange(y_min, y_max, 0.02))

        grid_df = pd.DataFrame(np.c_[xx.ravel(), yy.ravel()], columns=top2_cols)
        Z = dt_2d.predict(grid_df).reshape(xx.shape)

        fig, ax = plt.subplots(figsize=(9, 7))
        custom_cmap = ListedColormap(['#d4edda', '#ffeeba', '#cce5ff'])
        ax.contourf(xx, yy, Z, alpha=0.6, cmap=custom_cmap)

        palette = {'setosa': '#28a745', 'versicolor': '#e0a800', 'virginica': '#007bff'}
        for label, name in enumerate(self.target_names):
            idx_train = (self.y_train == label)
            ax.scatter(X_train_2d.loc[idx_train, top2_cols[0]], X_train_2d.loc[idx_train, top2_cols[1]],
                       c=palette[name], edgecolors='k', s=50, label=f'{name} (Train)', alpha=0.8)
            idx_test = (self.y_test == label)
            ax.scatter(X_test_2d.loc[idx_test, top2_cols[0]], X_test_2d.loc[idx_test, top2_cols[1]],
                       c=palette[name], edgecolors='red', s=110, marker='*', label=f'{name} (Test)', linewidth=1.2)

        ax.set_title("의사결정나무 모델의 2D 분류 결정 경계 (Decision Boundary)\n[Petal Length vs Petal Width]", fontsize=13, pad=15, fontweight='bold')
        ax.set_xlabel("petal length (cm)", fontsize=11)
        ax.set_ylabel("petal width (cm)", fontsize=11)
        ax.legend(bbox_to_anchor=(1.03, 1), loc="upper left", fontsize=10)
        plt.tight_layout()
        boundary_path = os.path.join(output_dir, 'iris_decision_boundary.png')
        plt.savefig(boundary_path, dpi=150)
        plt.close()
        print(f"[시각화 저장] 결정 경계면 차트: {boundary_path}")

    def save_model(self, filepath: str = 'model/iris_decision_tree.joblib'):
        """학습된 모델 파일 직렬화 저장"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(self.model, filepath)
        print(f"[모델 저장 완료] {filepath}")

    def predict_sample(self, sepal_len: float, sepal_wid: float, petal_len: float, petal_wid: float):
        """임의의 수치 입력 시 품종 및 확률 예측"""
        input_df = pd.DataFrame([[sepal_len, sepal_wid, petal_len, petal_wid]], columns=self.feature_cols)
        pred_idx = self.model.predict(input_df)[0]
        prob = self.model.predict_proba(input_df)[0]
        predicted_species = self.target_names[pred_idx]
        confidence = prob[pred_idx] * 100
        return {
            'predicted_species': predicted_species,
            'confidence': confidence,
            'probabilities': {name: float(p) for name, p in zip(self.target_names, prob)}
        }


def main():
    clf = IrisClassifier(max_depth=3)
    clf.load_and_split_data()
    clf.train()
    clf.evaluate()
    clf.benchmark_models()
    clf.save_visualizations()
    clf.save_model()

    # 샘플 예측 테스트
    sample_res = clf.predict_sample(5.1, 3.5, 1.4, 0.2)
    print("\n[샘플 예측 테스트]")
    print(f"  - 입력값: (5.1, 3.5, 1.4, 0.2)")
    print(f"  - 예측 결과: {sample_res['predicted_species']} (확신도: {sample_res['confidence']:.1f}%)")


if __name__ == '__main__':
    main()
