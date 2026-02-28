import Sidebar from '../components/Sidebar';
import TapeBar from '../components/TapeBar';

const DashboardLayout = ({
    children,
    tapeBarProps,
    pageTitleLine1,
    pageTitleLine2,
    headerRightContent
}) => {
    return (
        <>
            <TapeBar {...tapeBarProps} />
            <div className="app-container">
                <Sidebar />
                <main className="main-content">
                    {(pageTitleLine1 || pageTitleLine2 || headerRightContent) && (
                        <header className="content-header">
                            <h1 className="page-title">
                                {pageTitleLine1}<br />{pageTitleLine2}
                            </h1>
                            {headerRightContent && (
                                <div>
                                    {headerRightContent}
                                </div>
                            )}
                        </header>
                    )}
                    {children}
                </main>
            </div>
        </>
    );
};

export default DashboardLayout;
