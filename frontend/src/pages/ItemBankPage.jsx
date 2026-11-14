import QuestionForm from '../components/panels/QuestionForm';
import SectionHeader from '../components/common/SectionHeader';

export default function ItemBankPage() {
  return (
    <div className="dashboard">
      <SectionHeader title="Item Bank" subtitle="Submit questions to the encrypted item bank" />
      <QuestionForm />
    </div>
  );
}